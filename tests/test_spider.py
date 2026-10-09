from types import SimpleNamespace

import pytest
import scrapy
from scrapy.exceptions import IgnoreRequest
from scrapy.http import HtmlResponse
from scrapy.settings import Settings
from scrapy.statscollectors import MemoryStatsCollector

from reconspider.middleware import RequestBudget, ScopeGuard
from reconspider.passive.base import filter_results
from reconspider.spiders.universal import UniversalSpider


def spider(**kwargs):
    instance = UniversalSpider(target="https://example.com", **kwargs)
    crawler = SimpleNamespace(settings=Settings(), spider=instance)
    crawler.stats = MemoryStatsCollector(crawler)
    instance.crawler = crawler
    return instance


def test_redirect_rejects_external_host():
    instance = spider()
    response = HtmlResponse(
        "https://example.com/",
        status=302,
        headers={"Location": "https://evil.org/admin"},
        request=scrapy.Request("https://example.com/"),
    )
    results = list(instance.parse(response))
    assert not any(isinstance(r, scrapy.Request) for r in results)
    assert any(
        r.get("source") == "http_redirect" and not r["in_scope"]
        for r in results
        if isinstance(r, dict)
    )


def test_request_budget_and_depth():
    instance = spider(max_pages="1", max_depth="0")
    guard = RequestBudget.from_crawler(instance.crawler)
    guard.process_request(scrapy.Request("https://example.com/"))
    with pytest.raises(IgnoreRequest):
        guard.process_request(scrapy.Request("https://example.com/next"))
    assert instance.discover("/next", "html_anchor", "https://example.com/", 1)[1] is None


def test_guard_covers_internal_and_redirect_requests():
    instance = spider()
    guard = ScopeGuard.from_crawler(instance.crawler)
    for url in ["https://evil.org/", "http://169.254.169.254/latest/meta-data"]:
        with pytest.raises(IgnoreRequest):
            guard.process_request(scrapy.Request(url, meta={"dont_obey_robotstxt": True}))


def test_passive_filter_and_validation_default():
    instance = spider()
    records = [
        {"url": "https://example.com/old"},
        {"url": "https://evil.org/"},
        {"url": "https://example.com/old"},
    ]
    assert list(filter_results(records, instance.scope, 100)) == records[:1]
    item, request = instance.discover("/old", "wayback", "https://example.com/", 0, historical=True)
    assert item["historical"] and request is None


def test_cloud_boolean_arguments():
    instance = spider(include_subdomains="false", respect_robots="true")
    assert not instance.config.include_subdomains and instance.config.respect_robots
