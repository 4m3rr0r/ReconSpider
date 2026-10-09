import json
import logging
import time
from pathlib import Path

from reconspider.reports.html_report import generate_report
from reconspider.storage.sqlite import SQLiteStore


class InventoryPipeline:
    @classmethod
    def from_crawler(cls, crawler):
        instance = cls()
        instance.crawler = crawler
        return instance

    def open_spider(self):
        self.started = time.monotonic()
        config = self.crawler.spider.config
        self.stream = None
        self.store = SQLiteStore(config.sqlite) if config.sqlite else None
        if config.output:
            self.directory = Path(config.output)
            self.directory.mkdir(parents=True, exist_ok=True)
            self.path = self.directory / "crawl_results.jsonl"
            # Each execution is a fresh snapshot. JOBDIR resumes requests, not historical exports.
            resume = config.jobdir and (Path(config.jobdir) / "spider.state").exists()
            self.stream = self.path.open("a" if resume else "w", encoding="utf-8")

    def process_item(self, item):
        if self.stream:
            self.stream.write(json.dumps(dict(item), ensure_ascii=False, default=str) + "\n")
            self.stream.flush()
        if self.store:
            self.store.write(dict(item))
        return item

    def close_spider(self):
        # Requests filtered near shutdown may have audit events without another callback.
        for item in self.crawler.spider.events():
            self.process_item(item)
        if self.stream:
            metadata = {
                "kind": "run",
                "duration_seconds": round(time.monotonic() - self.started, 3),
                "stats": self.crawler.stats.get_stats(),
            }
            self.process_item(metadata)
            self.stream.close()
            try:
                generate_report(self.path, self.directory)
            except (OSError, ValueError) as exc:
                logging.getLogger(__name__).error("Report generation failed: %s", exc)
                self.crawler.stats.inc_value("recon/report_errors")
        if self.store:
            self.store.close()
