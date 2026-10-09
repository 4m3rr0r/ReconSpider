import re
from urllib.parse import urlsplit

RULES = [
    ("GraphQL", r"graphql"),
    ("Authentication", r"login|logout|auth|register|reset[-_]?password|signin|oauth"),
    ("File upload", r"upload"),
    ("File download", r"download|export"),
    ("Administrative interface", r"admin|dashboard|manage"),
    ("User management", r"users?|profile|account"),
    ("Search", r"search"),
    ("Redirect", r"redirect|callback"),
    ("API", r"(?:^|/)api(?:/|$)|swagger|openapi|/v\d+(?:/|$)"),
]


def classify(url, content_type=""):
    path = urlsplit(url).path.lower()
    categories = [name for name, pattern in RULES if re.search(pattern, path)]
    api = bool(re.search(r"(?:^|/)api(?:/|$)|graphql|swagger|openapi|/v\d+(?:/|$)", path))
    api = api or "json" in content_type or urlsplit(url).scheme in {"ws", "wss"}
    if api and "API" not in categories and "GraphQL" not in categories:
        categories.append("API")
    return {
        "categories": categories or ["General"],
        "is_api": api,
        "interesting": bool(categories),
        "classification_is_hint": True,
    }
