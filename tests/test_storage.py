import json

from reconspider.reports.diff import compare
from reconspider.reports.html_report import generate_report
from reconspider.storage.exporters import export_records, read_jsonl
from reconspider.storage.sqlite import SQLiteStore


def record(url):
    return {
        "kind": "url",
        "url": url,
        "in_scope": True,
        "parameters": [{"name": "id", "location": "query"}],
    }


def test_exports_and_sqlite(tmp_path):
    records = [record("https://example.com/?id=1")]
    for format in ["jsonl", "json", "csv", "txt"]:
        path = tmp_path / ("export." + format)
        export_records(records, path, format)
        assert "https://example.com/" in path.read_text()
    assert list(read_jsonl(tmp_path / "export.jsonl")) == records
    database = tmp_path / "history.sqlite"
    store = SQLiteStore(database)
    store.write(records[0])
    store.close()
    assert list(SQLiteStore.read(database)) == records


def test_comparison_and_report(tmp_path):
    old = [record("https://example.com/old")]
    new = [
        record("https://example.com/new"),
        {"kind": "form", "action": "/search", "method": "GET", "parameters": [{"name": "q"}]},
    ]
    diff = compare(old, new)
    assert diff["urls"]["added"] == ["https://example.com/new"]
    assert diff["urls"]["removed"] == ["https://example.com/old"]
    assert len(diff["forms"]["added"]) == 1
    path = tmp_path / "crawl_results.jsonl"
    export_records(new, path)
    summary = generate_report(path, tmp_path)
    assert summary["total_urls_discovered"] == 1
    assert summary["total_pages_fetched"] == 0
    assert "Search" in (tmp_path / "report.html").read_text()
    assert json.loads((tmp_path / "forms.json").read_text())[0]["method"] == "GET"


def test_report_escapes_untrusted_text(tmp_path):
    path = tmp_path / "crawl_results.jsonl"
    export_records([record("https://example.com/<script>alert(1)</script>")], path)
    generate_report(path, tmp_path)
    assert "<script>alert(1)</script>" not in (tmp_path / "report.html").read_text()
