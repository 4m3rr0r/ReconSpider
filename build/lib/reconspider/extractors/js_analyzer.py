"""Conservative static scanner: never evaluate JS or reconstruct dynamic values."""

import re
from urllib.parse import parse_qsl, urlsplit

# Match a complete literal, handling escapes and rejecting template interpolation.
LITERAL = re.compile(
    r"(?P<quote>['\"`])(?P<value>(?:\\.|(?! (?P=quote)).)*?)(?P=quote)", re.S | re.X
)
CONTEXT = re.compile(
    r"(?:fetch\s*\(|axios(?:\.(?:get|post|put|delete|patch|head))?\s*\(|\.open\s*\([^,]*,\s*|(?:import|URL|WebSocket)\s*\(?\s*)$",
    re.IGNORECASE,
)
PATH = re.compile(r"^(?:https?://|wss?://|//|/[^/]|\.{1,2}/)|^(?:api|graphql|v\d+)/", re.I)


def analyze_js(text, source_file="", limit=10000):
    results, seen = [], set()
    for match in LITERAL.finditer(text):
        value = match["value"]
        if "${" in value:
            continue
        value = value.replace(r"\/", "/")
        value = re.sub(
            r"\\(?:u([0-9a-fA-F]{4})|x([0-9a-fA-F]{2}))",
            lambda m: chr(int(m[1] or m[2], 16)),
            value,
        )
        context = text[max(0, match.start() - 100) : match.start()]
        explicit = bool(CONTEXT.search(context))
        if not PATH.search(value) and not (explicit and re.fullmatch(r"[\w./?=&%:-]+", value)):
            continue
        if len(value) > 8192 or value in seen:
            continue
        seen.add(value)
        params = [
            {"name": k, "source": "javascript_literal", "location": "query", "observed": False}
            for k in dict.fromkeys(k for k, _ in parse_qsl(urlsplit(value).query))
        ]
        # Infer static body field names near explicit fetch/axios calls; no values retained.
        if explicit:
            tail = text[match.end() : match.end() + 512].split(";", 1)[0]
            body = re.search(r"(?:body\s*:\s*JSON\.stringify\s*\(|data\s*:)\s*\{([^{}]*)\}", tail)
            if body:
                for key in re.findall(r"(?:^|,)\s*['\"]?([A-Za-z_$][\w$-]*)['\"]?\s*:", body[1]):
                    params.append(
                        {
                            "name": key,
                            "source": "javascript_object",
                            "location": "body",
                            "observed": False,
                        }
                    )
        binding = re.search(
            r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*new\s+URL\s*\(\s*$", context
        )
        if binding:
            suffix = text[match.end() : match.end() + 4096]
            expression = (
                re.escape(binding[1]) + r"\.searchParams\.(?:set|append)\s*\(\s*['\"]([^'\"]+)['\"]"
            )
            for name in dict.fromkeys(re.findall(expression, suffix)):
                params.append(
                    {
                        "name": name,
                        "source": "javascript_url_construction",
                        "location": "query",
                        "observed": False,
                    }
                )
        method = "GET"
        axios_method = re.search(
            r"axios\.(get|post|put|delete|patch|head)\s*\(\s*$", context, re.IGNORECASE
        )
        xhr_method = re.search(r"\.open\s*\(\s*['\"]([A-Z]+)['\"]\s*,\s*$", context, re.IGNORECASE)
        if axios_method or xhr_method:
            method = (axios_method or xhr_method)[1].upper()
        elif explicit:
            fetch_method = re.search(
                r"method\s*:\s*['\"]([A-Z]+)['\"]",
                text[match.end() : match.end() + 512].split(";", 1)[0],
                re.IGNORECASE,
            )
            if fetch_method:
                method = fetch_method[1].upper()
        results.append(
            {
                "url": value,
                "method": method,
                "source": "javascript",
                "source_file": source_file,
                "confidence": "high" if explicit else "medium",
                "parameters": params,
                "statically_inferred": True,
            }
        )
        if len(results) >= limit:
            break
    for match in re.finditer(r"[#@]\s*sourceMappingURL\s*=\s*(\S+)", text):
        if not match[1].startswith("data:"):
            results.append(
                {
                    "url": match[1],
                    "source": "source_map",
                    "source_file": source_file,
                    "confidence": "high",
                    "statically_inferred": True,
                }
            )
    return results
