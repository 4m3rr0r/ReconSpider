from urllib.parse import urlsplit

from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.exceptions import IgnoreRequest
from scrapy.utils.defer import deferred_to_future
from twisted.internet.task import deferLater

from reconspider.passive.base import PASSIVE_HOSTS


class ScopeGuard:
    @classmethod
    def from_crawler(cls, crawler):
        instance = cls()
        instance.crawler = crawler
        return instance

    def process_request(self, request):
        spider = self.crawler.spider
        parsed = urlsplit(request.url)
        if request.meta.get("passive_source"):
            allowed = (
                parsed.scheme == "https"
                and parsed.hostname in PASSIVE_HOSTS
                and parsed.port in {None, 443}
            )
            reason = "invalid_passive_destination"
        else:
            allowed, reason = spider.scope.check(request.url)
        if not allowed:
            spider.audit.append(
                {"kind": "skipped", "url": request.url, "reason": reason, "requested": False}
            )
            self.crawler.stats.inc_value("recon/skipped/" + reason)
            raise IgnoreRequest(reason)
        if request.meta.get("playwright"):
            # A browser has its own resolver and can fetch uncontrolled subresources.
            raise IgnoreRequest("browser networking requires an isolated egress policy")


class RequestBudget(ScopeGuard):
    def process_request(self, request):
        spider = self.crawler.spider
        if spider.request_count >= spider.config.max_pages:
            spider.audit.append(
                {"kind": "skipped", "url": request.url, "reason": "max_pages", "requested": False}
            )
            self.crawler.stats.inc_value("recon/skipped/max_pages")
            raise IgnoreRequest("max_pages")
        request.meta["recon_requested"] = True
        spider.request_count += 1
        spider.state["request_count"] = spider.request_count
        self.crawler.stats.inc_value("recon/requested")
        spider.audit.append(
            {
                "kind": "request",
                "url": request.url,
                "requested": True,
                "source": request.meta.get("passive_source", "crawl"),
                "attempt": request.meta.get("retry_times", 0) + 1,
            }
        )
        self.crawler.stats.set_value("recon/request_budget_used", spider.request_count)


class BackoffRetry(RetryMiddleware):
    async def process_response(self, request, response):
        result = super().process_response(request, response)
        if response.status in {429, 503} and result is not response:
            from twisted.internet import reactor

            retries = result.meta.get("retry_times", 1)
            delay = min(60, 2**retries)
            try:
                delay = max(delay, min(60, float(response.headers.get("Retry-After", b"0"))))
            except ValueError:
                pass
            await deferred_to_future(deferLater(reactor, delay, lambda: None))
        return result
