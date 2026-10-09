import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        value = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            value["exception"] = self.formatException(record.exc_info)
        return json.dumps(value, ensure_ascii=False)


class JsonLogging:
    @classmethod
    def from_crawler(cls, crawler):
        from scrapy import signals

        instance = cls()
        instance.configure()
        crawler.signals.connect(instance.configure, signal=signals.engine_started)
        return instance

    def configure(self):
        for handler in logging.getLogger().handlers:
            handler.setFormatter(JsonFormatter())
