BOT_NAME = "reconspider"
SPIDER_MODULES = ["reconspider.spiders"]
NEWSPIDER_MODULE = "reconspider.spiders"
USER_AGENT = "ReconSpider/0.1 (+authorized surface inventory)"
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 2.0
RANDOMIZE_DOWNLOAD_DELAY = False
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_MAX_DELAY = 60.0
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_MAXSIZE = 2097152
DOWNLOAD_WARNSIZE = 1048576
RETRY_TIMES = 2
RETRY_HTTP_CODES = [408, 429, 500, 502, 503, 504, 522, 524]
REDIRECT_ENABLED = False
METAREFRESH_ENABLED = False
HTTPERROR_ALLOW_ALL = True
COOKIES_ENABLED = False
TELNETCONSOLE_ENABLED = False
HTTPPROXY_ENABLED = False
DNS_RESOLVER = "reconspider.core.resolver.SafeResolver"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
DOWNLOADER_MIDDLEWARES = {
    "reconspider.middleware.ScopeGuard": 50,
    "reconspider.middleware.RequestBudget": 950,
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": None,
    "reconspider.middleware.BackoffRetry": 550,
}
ITEM_PIPELINES = {"reconspider.storage.pipeline.InventoryPipeline": 300}
LOG_LEVEL = "INFO"
# Standard log formatting is replaced by the JSON logging extension.
LOG_FORMAT = "%(levelname)s %(name)s %(message)s"
MEMUSAGE_LIMIT_MB = 768
MEMUSAGE_WARNING_MB = 512
FEED_EXPORT_ENCODING = "utf-8"
REQUEST_FINGERPRINTER_CLASS = "reconspider.core.fingerprinter.ExactFingerprinter"

DOWNLOADER_CLIENTCONTEXTFACTORY = "scrapy.core.downloader.contextfactory.BrowserLikeContextFactory"
EXTENSIONS = {"reconspider.logging.JsonLogging": 10}
DOWNLOAD_DELAY_JITTER = 0
