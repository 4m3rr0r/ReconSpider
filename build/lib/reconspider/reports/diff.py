import json
from urllib.parse import urlsplit


def inventory(records):
    result = {key: set() for key in ("urls", "parameters", "javascript", "api", "forms", "hosts")}
    for r in records:
        if r.get("kind") == "form":
            form = {
                "action": r.get("action"),
                "method": r.get("method"),
                "enctype": r.get("enctype"),
                "parameters": sorted(
                    (p["name"], p.get("type", "")) for p in r.get("parameters", [])
                ),
            }
            result["forms"].add(json.dumps(form, sort_keys=True))
        if r.get("kind") != "url" or not r.get("in_scope"):
            continue
        url = r["url"]
        result["urls"].add(url)
        result["hosts"].add(urlsplit(url).hostname)
        if urlsplit(url).path.endswith((".js", ".mjs")) or r.get("source") == "script_source":
            result["javascript"].add(url)
        if r.get("is_api"):
            result["api"].add(url)
        endpoint = r.get("endpoint_fingerprint", url.split("?", 1)[0])
        for p in r.get("parameters", []):
            result["parameters"].add(
                endpoint + " :: " + p["name"] + " :: " + p.get("location", "query")
            )
    return result


def compare(old, new):
    before, after = inventory(old), inventory(new)
    return {
        key: {
            "added": sorted(after[key] - before[key]),
            "removed": sorted(before[key] - after[key]),
        }
        for key in before
    }
