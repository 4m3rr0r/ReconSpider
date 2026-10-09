import json
from urllib.parse import urlencode

from reconspider.passive.base import passive_request


def request(host, callback, limit):
    query = urlencode(
        {
            "url": host + "/*",
            "output": "json",
            "fl": "timestamp,original",
            "collapse": "urlkey",
            "filter": "statuscode:200",
            "limit": limit,
        }
    )
    return passive_request("https://web.archive.org/cdx/search/cdx?" + query, callback, "wayback")


def parse(text):
    rows = json.loads(text)
    if not isinstance(rows, list):
        return
    for row in rows[1:]:
        if isinstance(row, list) and len(row) >= 2:
            yield {"url": row[1], "timestamp": row[0], "source": "wayback", "historical": True}
