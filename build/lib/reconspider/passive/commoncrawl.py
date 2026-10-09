import json
import re
from urllib.parse import urlencode

from reconspider.passive.base import passive_request


def request(host, callback, limit, index):
    if not re.fullmatch(r"CC-MAIN-\d{4}-\d{2}", index):
        raise ValueError("Invalid Common Crawl index ID")
    query = urlencode({"url": host + "/*", "output": "json", "pageSize": min(limit, 1000)})
    return passive_request(
        f"https://index.commoncrawl.org/{index}-index?{query}", callback, "commoncrawl"
    )


def parse(text):
    for line in text.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if "url" in record:
            yield {
                "url": record["url"],
                "timestamp": record.get("timestamp"),
                "source": "commoncrawl",
                "historical": True,
            }
