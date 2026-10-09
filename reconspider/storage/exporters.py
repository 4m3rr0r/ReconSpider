import csv
import json
from pathlib import Path


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    record = json.loads(line)
                    if not isinstance(record, dict):
                        raise ValueError("record must be an object")
                    yield record
                except ValueError as exc:
                    raise ValueError(f"{path}:{number}: invalid JSONL: {exc}") from exc


def export_records(records, path, format="jsonl"):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        if format == "jsonl":
            for item in records:
                stream.write(json.dumps(item, ensure_ascii=False) + "\n")
        elif format == "json":
            json.dump(list(records), stream, ensure_ascii=False, indent=2)
        elif format == "txt":
            for url in sorted({r["url"] for r in records if r.get("url")}):
                stream.write(url + "\n")
        elif format == "csv":
            fields = [
                "kind",
                "url",
                "source",
                "discovered_from",
                "in_scope",
                "status",
                "content_type",
                "parameters",
                "categories",
            ]
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for item in records:
                cells = {}
                for key in fields:
                    value = item.get(key, "")
                    value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                    # Prevent inventory text from becoming a spreadsheet formula.
                    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
                        value = "'" + value
                    cells[key] = value
                writer.writerow(cells)
        else:
            raise ValueError("Unsupported export format")
