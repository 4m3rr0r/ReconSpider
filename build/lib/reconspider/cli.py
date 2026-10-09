import argparse
import json
import logging
import sys
from pathlib import Path

import httpx

from reconspider.config import CrawlConfig, load_yaml
from reconspider.extractors.js_analyzer import analyze_js
from reconspider.reports.diff import compare
from reconspider.reports.html_report import generate_report
from reconspider.storage.exporters import export_records, read_jsonl
from reconspider.storage.external import transfer_snapshot
from reconspider.storage.sqlite import SQLiteStore


def parser():
    root = argparse.ArgumentParser(
        prog="reconspider", description="Authorized, scoped reconnaissance inventory"
    )
    commands = root.add_subparsers(dest="command", required=True)
    crawl = commands.add_parser("crawl", help="Crawl explicitly authorized targets")
    crawl.add_argument("--target", action="append")
    crawl.add_argument("--targets-file")
    crawl.add_argument("--scope-file")
    crawl.add_argument("--config")
    crawl.add_argument("--exclude", action="append")
    for name in ["include-subdomains", "allow-local", "source-maps", "validate-passive", "browser"]:
        crawl.add_argument("--" + name, action="store_true", default=None)
    crawl.add_argument(
        "--ignore-robots",
        action="store_true",
        default=None,
        help="Only when permitted by program rules",
    )
    for name in [
        "max-depth",
        "max-pages",
        "concurrency",
        "max-body-bytes",
        "passive-limit",
        "max-discoveries",
        "max-links-per-page",
    ]:
        crawl.add_argument("--" + name, type=int)
    for name in ["rate-limit", "timeout"]:
        crawl.add_argument("--" + name, type=float)
    crawl.add_argument("--passive", action="append", choices=["wayback", "commoncrawl", "urlscan"])
    crawl.add_argument("--commoncrawl-index")
    crawl.add_argument("--output")
    crawl.add_argument("--sqlite")
    crawl.add_argument("--jobdir")
    js = commands.add_parser("analyze-js", help="Analyze JS without executing it")
    js.add_argument("--file", required=True)
    export = commands.add_parser("export")
    export.add_argument("--input", default="output/crawl_results.jsonl")
    export.add_argument("--database", help="Read the latest SQLite crawl instead of JSONL")
    export.add_argument("--run-id")
    export.add_argument("--format", choices=["jsonl", "json", "csv", "txt"], default="jsonl")
    export.add_argument("--output")
    diff = commands.add_parser("diff")
    diff.add_argument("--old", required=True)
    diff.add_argument("--new", required=True)
    diff.add_argument("--output")
    report = commands.add_parser("report")
    report.add_argument("--input", default="output/crawl_results.jsonl")
    report.add_argument("--previous")
    report.add_argument("--output", default="output")
    sync = commands.add_parser(
        "sync", help="Transfer a snapshot using configured HTTPS object storage"
    )
    sync.add_argument("direction", choices=["push", "pull"])
    sync.add_argument("--file", default="output/crawl_results.jsonl")
    return root


def crawl_config(args):
    values = load_yaml(args.config) if args.config else {}
    if args.scope_file:
        scope = load_yaml(args.scope_file)
        if set(scope) - {"hosts", "exclude"}:
            raise ValueError("Scope file accepts only hosts and exclude")
        values["scope_hosts"] = scope.get("hosts", [])
        values["exclude"] = values.get("exclude", []) + scope.get("exclude", [])
    targets = list(values.get("targets", [])) + (args.target or [])
    if args.targets_file:
        targets.extend(
            line.strip()
            for line in Path(args.targets_file).read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    values["targets"] = targets
    for name in CrawlConfig.model_fields:
        if hasattr(args, name) and getattr(args, name) is not None:
            if name == "exclude":
                values[name] = values.get(name, []) + args.exclude
            else:
                values[name] = getattr(args, name)
    if args.ignore_robots:
        values["respect_robots"] = False
    values.setdefault("output", "output")
    if not targets:
        raise ValueError("Provide --target or --targets-file")
    return CrawlConfig.model_validate(values)


def main(argv=None):
    root = parser()
    args = root.parse_args(argv)
    try:
        if args.command == "crawl":
            from scrapy.crawler import CrawlerProcess
            from scrapy.settings import Settings

            from reconspider.spiders.universal import UniversalSpider

            cfg = crawl_config(args)
            settings = Settings()
            settings.setmodule("reconspider.settings", priority="project")
            settings.set("RECON_ALLOW_LOCAL", cfg.allow_local, priority="cmdline")
            from reconspider.logging import JsonFormatter

            handler = logging.StreamHandler()
            handler.setFormatter(JsonFormatter())
            handler.setLevel(settings.get("LOG_LEVEL", "INFO"))
            logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
            process = CrawlerProcess(settings, install_root_handler=False)
            deferred = process.crawl(UniversalSpider, config_json=cfg.model_dump_json())
            errors = []
            deferred.addErrback(lambda failure: errors.append(failure.getErrorMessage()))
            process.start()
            if errors:
                raise ValueError("; ".join(errors))
        elif args.command == "analyze-js":
            print(json.dumps(analyze_js(Path(args.file).read_text(), args.file), indent=2))
        elif args.command == "export":
            records = (
                SQLiteStore.read(args.database, args.run_id)
                if args.database
                else read_jsonl(args.input)
            )
            output = args.output or "output/export." + args.format
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            export_records(records, output, args.format)
            print(output)
        elif args.command == "diff":
            result = json.dumps(compare(read_jsonl(args.old), read_jsonl(args.new)), indent=2)
            if args.output:
                Path(args.output).write_text(result)
            else:
                print(result)
        elif args.command == "report":
            summary = generate_report(args.input, args.output, args.previous)
            print(json.dumps(summary, indent=2))
        elif args.command == "sync":
            transfer_snapshot(args.file, args.direction)
    except (ValueError, OSError, httpx.HTTPError) as exc:
        root.exit(2, f"reconspider: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
