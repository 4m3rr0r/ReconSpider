from urllib.parse import urljoin

from reconspider.core.classifier import classify
from reconspider.extractors.parameter_extractor import schema_parameters


def extract_openapi(document, base):
    if not isinstance(document, dict) or not ("openapi" in document or "swagger" in document):
        return []
    servers = document.get("servers", [])
    server_url = "/"
    if isinstance(servers, list) and servers and isinstance(servers[0], dict):
        candidate = servers[0].get("url", "/")
        server_url = candidate if isinstance(candidate, str) else "/"
    elif isinstance(document.get("basePath"), str):
        server_url = document["basePath"]
    server = urljoin(base, server_url)
    results = []
    for operation in schema_parameters(document):
        results.append(
            {
                "url": server.rstrip("/") + "/" + operation["path"].lstrip("/"),
                "source": "openapi",
                "method": operation["method"],
                "parameters": operation["parameters"],
                "statically_inferred": True,
                "speculative": "{" in operation["path"],
            }
        )
    return results


def is_api(url, content_type=""):
    return classify(url, content_type)["is_api"]
