import json
from collections import deque
from urllib.parse import urlsplit

import scrapy

from reconspider.config import CrawlConfig
from reconspider.core.classifier import classify
from reconspider.core.normalizer import fingerprints, normalize_url
from reconspider.core.scope import Scope
from reconspider.extractors.api_extractor import extract_openapi
from reconspider.extractors.html_extractor import (
    extract_html,
    extract_sitemap,
    json_urls,
    robots_sitemaps,
)
from reconspider.extractors.js_analyzer import analyze_js
from reconspider.extractors.parameter_extractor import nested_urls, query_parameters
from reconspider.passive import commoncrawl, urlscan, wayback


class UniversalSpider(scrapy.Spider):
    name = "universal"

    def __init__(self, target=None, targets=None, config_json=None, **kwargs):
        super().__init__()
        values = json.loads(config_json) if config_json else {}
        if target:
            values["targets"] = [target]
        if targets:
            values["targets"] = (
                json.loads(targets) if targets.startswith("[") else targets.split(",")
            )
        # Cloud arguments arrive as strings; validate rather than treating "false" as truthy.
        for key, value in kwargs.items():
            if key not in CrawlConfig.model_fields:
                raise ValueError(f"Unknown spider argument: {key}")
            if key in {"scope_hosts", "exclude", "passive"} and isinstance(value, str):
                value = json.loads(value) if value.startswith("[") else value.split(",")
            values[key] = value
        self.config = CrawlConfig.model_validate(values)
        if not self.config.targets:
            raise ValueError("Specify target or targets")
        if self.config.browser:
            raise ValueError(
                "Browser mode needs independently enforced browser egress; see docs/configuration.md"
            )
        self.scope = Scope(
            self.config.targets,
            self.config.scope_hosts,
            self.config.exclude,
            self.config.include_subdomains,
            self.config.allow_local,
        )
        for target_url in self.config.targets:
            if not self.scope.check(target_url)[0] or urlsplit(
                normalize_url(target_url)
            ).scheme not in {"http", "https"}:
                raise ValueError(f"Invalid or prohibited target: {target_url}")
        self.seen = set()
        self.scheduled = set()
        self.request_count = 0
        self.audit = deque()
        self.state = {}
        self.discovery_count = 0

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        cfg = spider.config
        for key, value in {
            "ROBOTSTXT_OBEY": cfg.respect_robots,
            "CONCURRENT_REQUESTS": cfg.concurrency,
            "DOWNLOAD_DELAY": 1 / cfg.rate_limit,
            "AUTOTHROTTLE_START_DELAY": 1 / cfg.rate_limit,
            "DOWNLOAD_TIMEOUT": cfg.timeout,
            "DOWNLOAD_MAXSIZE": cfg.max_body_bytes,
            "RECON_ALLOW_LOCAL": cfg.allow_local,
            "JOBDIR": cfg.jobdir,
            "DOWNLOAD_SLOTS": {
                "passive:" + host: {
                    "concurrency": 1,
                    "delay": max(5, 1 / cfg.rate_limit),
                    "randomize_delay": False,
                }
                for host in ("web.archive.org", "index.commoncrawl.org", "urlscan.io")
            },
            # Force Twisted: aiohttp handlers do not use our protected resolver.
            "DOWNLOAD_HANDLERS": {
                "http": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
                "https": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
            },
        }.items():
            crawler.settings.set(key, value, priority="spider")
        # CrawlerProcess creates its resolver using process settings, not spider settings.
        # This extension installs the correct filter on every engine startup (also Cloud).
        from scrapy import signals

        crawler.signals.connect(spider.install_resolver, signal=signals.engine_started)
        return spider

    def install_resolver(self):
        from twisted.internet import reactor

        from reconspider.core.resolver import SafeResolver

        original = reactor.nameResolver
        while isinstance(original, SafeResolver):
            original = original.original
        resolver = SafeResolver(reactor, self.config.allow_local)
        resolver.original = original
        resolver.install_on_reactor()

    def events(self):
        while self.audit:
            yield self.audit.popleft()

    def discover(self, raw, source, parent, depth, **extra):
        if self.discovery_count >= self.config.max_discoveries:
            self.crawler.stats.inc_value("recon/skipped/max_discoveries")
            return None, None
        self.discovery_count += 1
        self.state["discovery_count"] = self.discovery_count
        allowed, reason = self.scope.check(raw, parent)
        try:
            url = normalize_url(raw, parent)
        except (ValueError, UnicodeError):
            self.audit.append(
                {
                    "kind": "skipped",
                    "raw_url": raw[:8192],
                    "reason": "invalid_url",
                    "requested": False,
                }
            )
            return None, None
        item = {
            "kind": "url",
            "raw_url": raw,
            "url": url,
            "source": source,
            "discovered_from": parent,
            "depth": depth,
            "in_scope": allowed,
            "requested": False,
            "fetched": False,
            "skip_reason": None if allowed else reason,
            **fingerprints(url),
            **classify(url),
            **extra,
        }
        item["parameters"] = extra.get("parameters") or query_parameters(url)
        # Preserve provenance for repeated observations while requesting each identity once.
        self.seen.add(url)
        if not allowed:
            self.crawler.stats.inc_value("recon/out_of_scope")
            return item, None
        should_fetch = (
            urlsplit(url).scheme in {"http", "https"}
            and depth <= self.config.max_depth
            and not extra.get("speculative")
            and source != "form_action"
            and extra.get("method", "GET") in {"GET", "HEAD"}
            and (not extra.get("historical") or self.config.validate_passive)
            and (source != "source_map" or self.config.source_maps)
        )
        if allowed and not should_fetch:
            item["skip_reason"] = (
                "depth_limit"
                if depth > self.config.max_depth
                else "speculative_reference"
                if extra.get("speculative")
                else "form_not_submitted"
                if source == "form_action"
                else "method_metadata_only"
                if extra.get("method", "GET") not in {"GET", "HEAD"}
                else "historical_not_validated"
                if extra.get("historical")
                else "source_map_disabled"
                if source == "source_map"
                else "unsupported_transport"
            )
        if (
            allowed
            and should_fetch
            and url not in self.scheduled
            and len(self.scheduled) >= self.config.max_pages
        ):
            item["skip_reason"] = "max_pages"
        if (
            should_fetch
            and url not in self.scheduled
            and len(self.scheduled) < self.config.max_pages
        ):
            self.scheduled.add(url)
            return item, scrapy.Request(
                url,
                callback=self.parse,
                errback=self.failed,
                meta={
                    "recon_depth": depth,
                    "handle_httpstatus_all": True,
                    "redirect_hops": extra.get("redirect_hops", 0),
                },
                dont_filter=False,
            )
        return item, None

    async def start(self):
        self.scheduled = self.state.setdefault("scheduled", set())
        self.seen = self.state.setdefault("seen", set())
        self.request_count = self.state.get("request_count", 0)
        self.discovery_count = self.state.get("discovery_count", 0)
        for target in self.config.targets:
            item, request = self.discover(target, "seed", None, 0)
            if item:
                yield item
            if request:
                yield request
            parsed = urlsplit(normalize_url(target))
            origin = f"{parsed.scheme}://{parsed.netloc}"
            for path in ("/robots.txt", "/sitemap.xml"):
                item, request = self.discover(origin + path, "standard_metadata", target, 0)
                if item:
                    yield item
                if request:
                    yield request
            host = parsed.hostname
            for source in self.config.passive:
                module = {"wayback": wayback, "commoncrawl": commoncrawl, "urlscan": urlscan}[
                    source
                ]
                arguments = [host, self.parse_passive, self.config.passive_limit]
                if source == "commoncrawl":
                    arguments.append(self.config.commoncrawl_index)
                request = module.request(*arguments)
                request.errback = self.failed
                yield request

    def failed(self, failure):
        from scrapy.exceptions import IgnoreRequest

        yield from self.events()
        skipped = bool(failure.check(IgnoreRequest))
        self.crawler.stats.inc_value("recon/skipped/request" if skipped else "recon/errors")
        yield {
            "kind": "skipped" if skipped else "error",
            "url": failure.request.url,
            "reason" if skipped else "error": failure.getErrorMessage(),
            "fetched": False,
            "requested": bool(failure.request.meta.get("recon_requested")),
        }

    def parse_passive(self, response):
        yield from self.events()
        source = response.meta["passive_source"]
        if response.status != 200:
            yield {
                "kind": "error",
                "url": response.url,
                "source": source,
                "status": response.status,
                "error": "passive API returned non-success",
            }
            return
        module = {"wayback": wayback, "commoncrawl": commoncrawl, "urlscan": urlscan}[source]
        try:
            for index, record in enumerate(module.parse(response.text)):
                if index >= self.config.passive_limit:
                    break
                raw = record.pop("url")
                item, request = self.discover(raw, record.pop("source"), response.url, 0, **record)
                if item:
                    yield item
                if request:
                    yield request
        except (ValueError, TypeError, KeyError):
            yield {"kind": "error", "url": response.url, "error": "invalid passive response"}

    def parse(self, response):
        yield from self.events()
        depth = response.meta.get("recon_depth", 0)
        ctype = response.headers.get("Content-Type", b"").decode("latin1").split(";", 1)[0]
        yield {
            "kind": "response",
            "url": response.url,
            "status": response.status,
            "content_type": ctype,
            "requested": True,
            "fetched": True,
            "successful": 200 <= response.status < 300,
            "depth": depth,
            **classify(response.url, ctype),
        }
        self.crawler.stats.inc_value("recon/fetched")
        if response.status in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            hops = response.meta.get("redirect_hops", 0)
            if location:
                item, request = self.discover(
                    location.decode("latin1"),
                    "http_redirect",
                    response.url,
                    depth,
                    redirect_hops=hops + 1,
                )
                if item:
                    if hops >= 10:
                        item["skip_reason"] = "max_redirects"
                    yield item
                if request and hops < 10:
                    yield request
            return
        if not 200 <= response.status < 300:
            return
        if not hasattr(response, "text"):
            return
        links = []
        if urlsplit(response.url).path == "/robots.txt":
            links = robots_sitemaps(response.text)
        elif "xml" in ctype or response.text.lstrip().startswith(
            ("<?xml", "<urlset", "<sitemapindex")
        ):
            links = extract_sitemap(response, self.config.max_links_per_page)
        elif "javascript" in ctype or urlsplit(response.url).path.endswith((".js", ".mjs")):
            links = analyze_js(response.text, response.url, self.config.max_links_per_page)
        elif "json" in ctype or urlsplit(response.url).path.endswith(".map"):
            try:
                data = json.loads(response.text)
                links = extract_openapi(data, response.url)
                links += [{"url": url, "source": "json_reference"} for url in json_urls(data)]
                if self.config.source_maps and isinstance(data, dict):
                    for content in data.get("sourcesContent", [])[:100]:
                        if isinstance(content, str):
                            links += analyze_js(content, response.url)
            except (ValueError, TypeError, RecursionError):
                self.crawler.stats.inc_value("recon/extraction_errors")
        elif "html" in ctype or "<html" in response.text[:1024].lower():
            links, forms = extract_html(response, self.config.max_links_per_page)
            for form in forms:
                form["in_scope"] = self.scope.check(form["action"])[0]
                yield {"kind": "form", **form}
        for link in list(links[: self.config.max_links_per_page]):
            links.extend(
                {"url": value, "source": "nested_query"} for value in nested_urls(link["url"])
            )
        for link in links[: self.config.max_links_per_page]:
            raw, source = link.pop("url"), link.pop("source")
            item, request = self.discover(raw, source, response.url, depth + 1, **link)
            if item:
                yield item
            if request:
                yield request
