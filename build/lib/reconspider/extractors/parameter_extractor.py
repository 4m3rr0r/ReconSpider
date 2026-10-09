import json
from urllib.parse import parse_qsl, urlsplit


def query_parameters(url):
    # Preserve duplicate keys in URL identity; inventory names only once.
    return [
        {"name": name, "source": "query_string", "location": "query", "observed": True}
        for name in dict.fromkeys(
            k for k, _ in parse_qsl(urlsplit(url).query, keep_blank_values=True)
        )
    ]


def _mapping(value):
    return value if isinstance(value, dict) else {}


def schema_parameters(document):
    results = []
    for path, methods in _mapping(_mapping(document).get("paths")).items():
        if not isinstance(path, str) or not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            if method.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "head",
                "options",
            } or not isinstance(operation, dict):
                continue
            params = []
            for collection in (methods.get("parameters", []), operation.get("parameters", [])):
                if not isinstance(collection, list):
                    continue
                for p in collection:
                    if isinstance(p, dict) and isinstance(p.get("name"), str):
                        params.append(
                            {
                                "name": p["name"],
                                "location": p.get("in", "unknown"),
                                "source": "openapi",
                                "observed": False,
                            }
                        )
            body = _mapping(_mapping(operation.get("requestBody")).get("content"))
            for media in body.values():
                for name in _mapping(_mapping(_mapping(media).get("schema")).get("properties")):
                    params.append(
                        {"name": name, "location": "body", "source": "openapi", "observed": False}
                    )
            results.append({"path": path, "method": method.upper(), "parameters": params})
    return results


def static_body_parameters(text):
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return []
    if not isinstance(value, dict):
        return []
    return [
        {"name": k, "source": "static_json", "location": "body", "observed": False} for k in value
    ]


def nested_urls(url, limit=20):
    """Observed URLs carried in query values; scope is applied by the caller."""
    result, pending, seen = [], [(url, 0)], set()
    while pending and len(result) < limit:
        current, depth = pending.pop()
        if depth >= 3:
            continue
        for _, value in parse_qsl(urlsplit(current).query, keep_blank_values=True):
            if value.startswith(("https://", "http://", "//", "/")) and value not in seen:
                seen.add(value)
                result.append(value)
                pending.append((value, depth + 1))
    return result[:limit]
