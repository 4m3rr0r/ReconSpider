import asyncio
import json

import pytest
import scrapy
from scrapy.http import Response

from reconspider.cli import crawl_config, parser
from reconspider.config import CrawlConfig
from reconspider.extractors.js_analyzer import analyze_js
from reconspider.extractors.parameter_extractor import nested_urls
from reconspider.middleware import BackoffRetry
from reconspider.passive import commoncrawl, urlscan, wayback
from reconspider.storage.pipeline import InventoryPipeline
from reconspider.storage.sqlite import SQLiteStore
from tests.test_spider import spider


def test_encoded_absolute_url_exclusion():
    instance = spider(exclude='["https://example.com/private*"]')
    assert not instance.scope.check("https://example.com/%70rivate/a")[0]


def test_discovery_budget():
    instance = spider(max_discoveries="1")
    assert instance.discover("/a", "html_anchor", "https://example.com", 1)[0]
    assert instance.discover("/b", "html_anchor", "https://example.com", 1) == (None, None)


def test_form_actions_and_websockets_are_inventory_only():
    instance = spider()
    assert instance.discover("/submit", "form_action", "https://example.com", 1)[1] is None
    assert (
        instance.discover("wss://example.com/socket", "javascript", "https://example.com", 1)[1]
        is None
    )


def test_source_map_opt_in():
    instance = spider()
    assert instance.discover("/app.js.map", "source_map", "https://example.com", 1)[1] is None
    opted_in = spider(source_maps="true")
    assert opted_in.discover("/app.js.map", "source_map", "https://example.com", 1)[1]


def test_js_does_not_mistake_adjacent_credentials_for_endpoints():
    result = analyze_js('fetch("/api", {headers: {Authorization: "secret-token"}});')
    assert [r["url"] for r in result] == ["/api"]


def test_nested_query_url():
    urls = nested_urls("https://example.com/?redirect=https%3A%2F%2Fother.org%2F%3Fid%3D1")
    assert urls == ["https://other.org/?id=1"]


def test_cli_limits_and_config_validation():
    config = crawl_config(
        parser().parse_args(
            [
                "crawl",
                "--target",
                "https://example.com",
                "--max-discoveries",
                "10",
                "--max-links-per-page",
                "3",
            ]
        )
    )
    assert config.max_discoveries == 10 and config.max_links_per_page == 3
    with pytest.raises(ValueError):
        CrawlConfig(rate_limit=0)
    with pytest.raises(ValueError):
        CrawlConfig(passive=["unknown"])


def test_passive_provider_decoders():
    assert (
        list(
            wayback.parse(
                json.dumps([["timestamp", "original"], ["20260101", "https://example.com/a"]])
            )
        )[0]["timestamp"]
        == "20260101"
    )
    assert list(commoncrawl.parse('{"url":"https://example.com/a","timestamp":"20260101"}'))[0][
        "historical"
    ]
    assert (
        list(
            urlscan.parse(
                '{"results":[{"page":{"url":"https://example.com/a"},"task":{"time":"2026-01-01"}}]}'
            )
        )[0]["source"]
        == "urlscan"
    )


def test_backoff_retry_is_bounded_and_403_is_not_retried(monkeypatch):
    instance = spider()
    instance.crawler.settings.set("RETRY_TIMES", 2)
    instance.crawler.settings.set("RETRY_HTTP_CODES", [429, 503])
    instance.crawler.settings.set("RETRY_PRIORITY_ADJUST", -1)
    instance.crawler.settings.set("RETRY_EXCEPTIONS", [])
    retry = BackoffRetry.from_crawler(instance.crawler)
    delays = []
    monkeypatch.setattr(
        "reconspider.middleware.deferLater", lambda reactor, delay, f: delays.append(delay)
    )

    async def fake_wait(value):
        return None

    monkeypatch.setattr("reconspider.middleware.deferred_to_future", fake_wait)
    request = scrapy.Request("https://example.com/")
    response = Response(request.url, status=429, headers={"Retry-After": "3"}, request=request)
    second = asyncio.run(retry.process_response(request, response))
    third = asyncio.run(retry.process_response(second, response))
    last = asyncio.run(retry.process_response(third, response))
    assert second.meta["retry_times"] == 1 and third.meta["retry_times"] == 2
    assert last is response and delays == [3, 4]
    forbidden = Response(request.url, status=403, request=request)
    assert asyncio.run(retry.process_response(request, forbidden)) is forbidden


def test_pipeline_metadata_and_sqlite_shutdown(tmp_path):
    instance = spider(output=str(tmp_path), sqlite=str(tmp_path / "history.sqlite"))
    pipeline = InventoryPipeline.from_crawler(instance.crawler)
    pipeline.open_spider()
    pipeline.process_item(
        {"kind": "url", "url": "https://example.com", "parameters": [], "in_scope": True}
    )
    pipeline.close_spider()
    records = list(SQLiteStore.read(tmp_path / "history.sqlite"))
    assert records[-1]["kind"] == "run"
    assert (tmp_path / "summary.json").exists()


def test_post_route_metadata_is_not_requested():
    records = analyze_js('axios.post("/api/update");fetch("/api/create",{method:"POST"});')
    assert all(record["method"] == "POST" for record in records)
    instance = spider()
    assert (
        instance.discover("/api/update", "javascript", "https://example.com", 1, method="POST")[1]
        is None
    )


def test_url_constructor_parameter_names():
    records = analyze_js(
        'const u=new URL("/api/users",location.origin);u.searchParams.set("page",2);u.searchParams.append("search",q);'
    )
    assert {p["name"] for p in records[0]["parameters"]} == {"page", "search"}
    assert all(not p["observed"] for p in records[0]["parameters"])


def test_malformed_openapi_fields_do_not_abort_extraction():
    from reconspider.extractors.api_extractor import extract_openapi

    assert extract_openapi({"openapi": "3.0.0", "paths": []}, "https://example.com/spec") == []
    records = extract_openapi(
        {
            "openapi": "3.0.0",
            "servers": [None],
            "paths": {"/api": {"get": {"parameters": None, "requestBody": None}}},
        },
        "https://example.com/spec",
    )
    assert records[0]["url"] == "https://example.com/api" and records[0]["parameters"] == []


def test_parameters_do_not_leak_between_js_calls():
    records = analyze_js(
        'fetch("/api/users?page=2");axios.post("/api/profile", {data:{displayName:"x"}});'
    )
    assert [p["name"] for p in records[0]["parameters"]] == ["page"]
    assert [p["name"] for p in records[1]["parameters"]] == ["displayName"]
