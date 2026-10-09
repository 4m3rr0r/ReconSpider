import html
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from reconspider.reports.diff import compare
from reconspider.storage.exporters import read_jsonl


def generate_report(input_path, output, previous=None):
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    records = list(read_jsonl(input_path))
    urls = [r for r in records if r.get("kind") == "url"]
    responses = [r for r in records if r.get("kind") == "response"]
    forms = [r for r in records if r.get("kind") == "form"]
    params = [
        {"endpoint": r.get("endpoint_fingerprint", r["url"]), "parameters": r["parameters"]}
        for r in urls
        if r.get("parameters")
    ]
    params.extend(
        {"endpoint": f["action"], "parameters": f["parameters"]}
        for f in forms
        if f.get("parameters")
    )
    javascript = {
        r["url"]
        for r in urls
        if r.get("source") == "script_source" or urlsplit(r["url"]).path.endswith((".js", ".mjs"))
    }
    api = {r["url"] for r in urls if r.get("is_api")}
    texts = {
        "all_urls.txt": [r["url"] for r in urls],
        "unique_urls.txt": sorted({r["url"] for r in urls}),
        "urls_with_parameters.txt": sorted({r["url"] for r in urls if r.get("parameters")}),
        "javascript_files.txt": sorted(javascript),
        "api_endpoints.txt": sorted(api),
        "interesting_endpoints.txt": sorted({r["url"] for r in urls if r.get("interesting")}),
        "out_of_scope_references.txt": sorted({r["url"] for r in urls if not r.get("in_scope")}),
    }
    for filename, lines in texts.items():
        (directory / filename).write_text("\n".join(lines) + ("\n" if lines else ""))
    for filename, data in {"parameters.json": params, "forms.json": forms}.items():
        (directory / filename).write_text(json.dumps(data, indent=2))
    runs = [r for r in records if r.get("kind") == "run"]
    summary = {
        "total_urls_discovered": len({r["url"] for r in urls}),
        "total_discovery_observations": len(urls),
        "total_requests": sum(r.get("kind") == "request" for r in records),
        "total_pages_fetched": len(responses),
        "successful_urls": len({r["url"] for r in responses if r.get("successful")}),
        "unique_parameter_names": sorted({p["name"] for r in params for p in r["parameters"]}),
        "javascript_files": len(javascript),
        "forms": len(forms),
        "api_endpoints": len(api),
        "http_status_distribution": dict(Counter(str(r["status"]) for r in responses)),
        "endpoint_categories": dict(Counter(c for r in urls for c in r.get("categories", []))),
        "duration_seconds": runs[-1].get("duration_seconds") if runs else None,
        "errors": [r for r in records if r.get("kind") == "error"],
        "skipped_urls": [r for r in records if r.get("kind") == "skipped" or r.get("skip_reason")],
    }
    changes = compare(read_jsonl(previous), records) if previous else None
    summary["comparison"] = changes
    (directory / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    observed = {r["url"]: r for r in responses}
    requested = {r["url"] for r in records if r.get("kind") == "request"}
    rows = []
    for record in urls:
        response = observed.get(record["url"], {})
        stage = (
            "fetched" if response else "requested" if record["url"] in requested else "discovered"
        )
        cells = [
            record["url"],
            record.get("source", ""),
            str(record.get("in_scope", False)),
            stage,
            str(response.get("status", "")),
            ", ".join(record.get("categories", [])),
        ]
        rows.append(
            "<tr>" + "".join("<td>" + html.escape(cell) + "</td>" for cell in cells) + "</tr>"
        )
    document = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>ReconSpider inventory</title><style>
body{font:15px system-ui;margin:2rem;background:#f5f7fa;color:#172b4d}
table{border-collapse:collapse;width:100%;background:white}td,th{padding:8px;border:1px solid #dde2eb;text-align:left;overflow-wrap:anywhere}input,select{padding:8px;margin:8px}pre{white-space:pre-wrap}td:first-child{max-width:600px}
</style><h1>ReconSpider inventory</h1><p>Classification hints describe attack surface; they do not establish vulnerabilities. Historical references do not establish current availability.</p>
<label>Search <input id="search" type="search"></label><label>Stage <select id="stage"><option value="">All</option><option>discovered</option><option>requested</option><option>fetched</option></select></label>
<label>Scope <select id="scope"><option value="">All</option><option value="True">In scope</option><option value="False">Out of scope</option></select></label>
<h2>Summary</h2><pre>SUMMARY</pre><h2>Discovered URLs</h2><table><thead><tr><th>URL</th><th>Source</th><th>Scope</th><th>Stage</th><th>Status</th><th>Categories</th></tr></thead><tbody>ROWS</tbody></table>
<script>function filter(){const q=document.getElementById('search').value.toLowerCase();const stage=document.getElementById('stage').value;const scope=document.getElementById('scope').value;for(const r of document.querySelectorAll('tbody tr')){r.hidden=!r.textContent.toLowerCase().includes(q)||(stage&&r.cells[3].textContent!==stage)||(scope&&r.cells[2].textContent!==scope)}}for(const id of ['search','stage','scope'])document.getElementById(id).addEventListener('input',filter);</script></html>"""
    # Assemble once so inventory strings cannot be interpreted as placeholders.
    before, remaining = document.split("SUMMARY", 1)
    middle, after = remaining.split("ROWS", 1)
    document = (
        before
        + html.escape(json.dumps(summary, indent=2, default=str))
        + middle
        + "".join(rows)
        + after
    )
    (directory / "report.html").write_text(document)
    return summary
