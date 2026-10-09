import json
import re
from urllib.parse import urljoin

from reconspider.extractors.form_extractor import extract_forms
from reconspider.extractors.js_analyzer import analyze_js

ATTRIBUTES = {
    "a": ("href", "html_anchor"),
    "area": ("href", "html_anchor"),
    "iframe": ("src", "iframe"),
    "form": ("action", "form_action"),
    "script": ("src", "script_source"),
    "link": ("href", "html_link"),
    "img": ("src", "media"),
    "video": ("src", "media"),
    "audio": ("src", "media"),
    "source": ("src", "media"),
    "object": ("data", "media"),
}


def json_urls(value, limit=10000):
    # Bound work even for adversarial embedded JSON.
    stack, count = [value], 0
    while stack and count < limit:
        item = stack.pop()
        count += 1
        if isinstance(item, dict):
            stack.extend(list(item.values())[:limit])
        elif isinstance(item, list):
            stack.extend(item[:limit])
        elif isinstance(item, str) and re.match(r"^(?:https?://|wss?://|/|\.{1,2}/)", item):
            yield item


def extract_html(response, limit=10000):
    links = []
    base = response.url
    candidate = response.css("base::attr(href)").get()
    if candidate:
        base = urljoin(base, candidate)
    for element in response.css("*"):
        tag = element.root.tag
        if tag in ATTRIBUTES:
            attr, source = ATTRIBUTES[tag]
            if element.attrib.get(attr):
                if tag == "link" and "canonical" in element.attrib.get("rel", ""):
                    source = "canonical"
                links.append({"url": element.attrib[attr], "source": source})
        for attr, value in element.attrib.items():
            if attr.startswith("data-") and re.match(r"^(?:https?://|/|\.{1,2}/)", value):
                links.append({"url": value, "source": "data_attribute"})
            if attr == "srcset":
                for part in value.split(","):
                    if part.strip():
                        links.append({"url": part.strip().split()[0], "source": "media"})
        if tag == "meta" and element.attrib.get("http-equiv", "").lower() == "refresh":
            match = re.search(r"url\s*=\s*['\"]?([^'\"]+)", element.attrib.get("content", ""), re.I)
            if match:
                links.append({"url": match[1].strip(), "source": "meta_refresh"})
        if len(links) >= limit:
            break
    for script in response.css("script:not([src])"):
        text = script.xpath("string(.)").get() or ""
        if "json" in script.attrib.get("type", ""):
            try:
                links.extend(
                    {"url": url, "source": "embedded_json"}
                    for url in json_urls(json.loads(text), limit)
                )
            except (ValueError, RecursionError):
                pass
        else:
            links.extend(analyze_js(text, response.url, limit))
    for link in links[:limit]:
        link["url"] = urljoin(base, link["url"])
    return links[:limit], extract_forms(response, base)[:limit]


def extract_sitemap(response, limit=10000):
    return [
        {"url": url, "source": "sitemap"}
        for url in response.xpath('//*[local-name()="loc"]/text()').getall()[:limit]
    ]


def robots_sitemaps(text):
    return [
        {"url": m[1].strip(), "source": "robots_sitemap"}
        for m in re.finditer(r"^\s*Sitemap:\s*(\S+)", text, re.I | re.M)
    ]
