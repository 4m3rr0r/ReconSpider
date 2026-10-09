from urllib.parse import urlsplit

import scrapy
import tldextract

# Use the bundled PSL: no surprise network downloads.
EXTRACT = tldextract.TLDExtract(suffix_list_urls=())
PASSIVE_HOSTS = {"web.archive.org", "index.commoncrawl.org", "urlscan.io"}


def passive_request(url, callback, source, headers=None):
    return scrapy.Request(
        url,
        callback=callback,
        headers=headers or {},
        meta={
            "passive_source": source,
            "download_slot": "passive:" + urlsplit(url).hostname,
            "dont_obey_robotstxt": True,
            "allow_offsite": True,
        },
        dont_filter=True,
    )


def filter_results(records, scope, limit):
    seen = set()
    for record in records:
        url = record.get("url", "")
        allowed, _ = scope.check(url)
        if allowed and url not in seen:
            seen.add(url)
            yield record
            if len(seen) >= limit:
                break
