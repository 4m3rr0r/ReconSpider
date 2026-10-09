import json
import os
from urllib.parse import urlencode

from reconspider.passive.base import passive_request


def request(host, callback, limit):
    headers = (
        {"api-key": os.environ["URLSCAN_API_KEY"]} if os.environ.get("URLSCAN_API_KEY") else {}
    )
    query = urlencode({"q": "domain:" + host, "size": min(limit, 100)})
    return passive_request(
        "https://urlscan.io/api/v1/search/?" + query, callback, "urlscan", headers
    )


def parse(text):
    for record in json.loads(text).get("results", []):
        if record.get("page", {}).get("url"):
            yield {
                "url": record["page"]["url"],
                "timestamp": record.get("task", {}).get("time"),
                "source": "urlscan",
                "historical": True,
            }
