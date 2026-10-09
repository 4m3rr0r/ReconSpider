from scrapy.http import HtmlResponse, XmlResponse

from reconspider.extractors.api_extractor import extract_openapi
from reconspider.extractors.html_extractor import extract_html, extract_sitemap, robots_sitemaps
from reconspider.extractors.js_analyzer import analyze_js
from reconspider.extractors.parameter_extractor import query_parameters


def test_html_and_forms():
    response = HtmlResponse(
        "https://example.com/",
        body=b'<html><a href="/a">A</a><iframe src="/frame"></iframe><meta http-equiv="refresh" content="0;url=/refresh"><div data-api="/api"></div><script type="application/json">{"url":"/json"}</script><form method="post" action="/submit"><input name="secret" value="do-not-record"><textarea name="description"></textarea></form></html>',
        encoding="utf-8",
    )
    links, forms = extract_html(response)
    urls = {r["url"] for r in links}
    assert {
        "https://example.com/a",
        "https://example.com/frame",
        "https://example.com/refresh",
        "https://example.com/api",
        "https://example.com/json",
    } <= urls
    assert forms[0]["method"] == "POST"
    assert forms[0]["parameters"][0]["name"] == "secret"
    assert "do-not-record" not in str(forms)
    assert not forms[0]["submitted"]


def test_js_minified():
    text = 'fetch("/api/users?id=1",{body:JSON.stringify({name:"x",page:2})});axios.get("/api/profile");x.open("GET","/download");$.ajax({url:"/ajax"});const p="/admin/dashboard";new URL("/url",location.origin);import("./chunk.js");new WebSocket("wss://example.com/socket");const a=`/dynamic/${id}`;'
    records = analyze_js(text, "app.js")
    urls = {r["url"] for r in records}
    assert {
        "/api/users?id=1",
        "/api/profile",
        "/download",
        "/ajax",
        "/admin/dashboard",
        "/url",
        "./chunk.js",
        "wss://example.com/socket",
    } <= urls
    assert not any("${" in url for url in urls)
    assert {p["name"] for p in records[0]["parameters"]} == {"id", "name", "page"}
    assert records[0]["source_file"] == "app.js"


def test_sitemap_robots():
    response = XmlResponse(
        "https://example.com/sitemap.xml",
        body=b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://example.com/map.xml</loc></sitemap></sitemapindex>',
        encoding="utf-8",
    )
    assert extract_sitemap(response)[0]["url"] == "https://example.com/map.xml"
    assert robots_sitemaps("Sitemap: https://example.com/map.xml")[0]["source"] == "robots_sitemap"


def test_query_and_openapi():
    assert len(query_parameters("https://example.com/?id=1&id=2&empty=")) == 2
    result = extract_openapi(
        {
            "openapi": "3.0.0",
            "paths": {"/users/{id}": {"get": {"parameters": [{"name": "id", "in": "path"}]}}},
        },
        "https://example.com/openapi.json",
    )
    assert result[0]["speculative"] and not result[0]["parameters"][0]["observed"]
