import posixpath
import re
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit

_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def _escapes(value):
    def replace(match):
        char = chr(int(match[1], 16))
        return char if char in _UNRESERVED else "%" + match[1].upper()

    return re.sub(r"%([0-9a-fA-F]{2})", replace, value)


def normalize_url(raw: str, base: str | None = None) -> str:
    raw = raw.strip()
    if re.search(r"[\x00-\x20\x7f\\]", raw):
        raise ValueError("Control characters, spaces and backslashes are not valid URL input")
    if raw.lower().startswith(("http%3a", "https%3a", "%2f")):
        raw = unquote(raw)
    parts = urlsplit(urljoin(base or "", raw))
    if parts.scheme.lower() not in {"http", "https", "ws", "wss"}:
        raise ValueError("Unsupported URL scheme")
    if not parts.hostname or parts.username is not None or parts.password is not None:
        raise ValueError("Missing host or embedded credentials")
    host = parts.hostname.rstrip(".").encode("idna").decode().lower()
    if ":" in host:
        host = f"[{host}]"
    port = parts.port
    scheme = parts.scheme.lower()
    authority = (
        host
        if port is None or port == (443 if scheme in {"https", "wss"} else 80)
        else f"{host}:{port}"
    )
    path = _escapes(parts.path or "/")
    # RFC-style dot segment removal while retaining repeated slashes.
    segments = []
    for segment in path.split("/"):
        if segment == "..":
            if len(segments) > 1:
                segments.pop()
        elif segment != ".":
            segments.append(segment)
    path = "/".join(segments)
    if parts.path.endswith(("/.", "/..")) and not path.endswith("/"):
        path += "/"
    if not path.startswith("/"):
        path = "/" + path
    return urlunsplit((scheme, authority, path or "/", _escapes(parts.query), ""))


def fingerprints(url):
    p = urlsplit(url)
    keys = [key for key, _ in parse_qsl(p.query, keep_blank_values=True)]
    endpoint = urlunsplit((p.scheme, p.netloc, p.path, "", ""))
    pattern = endpoint + ("?" + urlencode([(key, "VALUE") for key in keys]) if keys else "")
    return {"endpoint_fingerprint": endpoint, "parameter_fingerprint": pattern}


def path_for_scope(url):
    # Decode repeatedly to prevent encoded traversal/exclusion bypasses.
    path = urlsplit(url).path
    for _ in range(5):
        decoded = unquote(path)
        if decoded == path:
            break
        path = decoded
    return posixpath.normpath(path.replace("\\", "/"))
