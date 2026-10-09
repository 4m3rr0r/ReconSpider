import fnmatch
import ipaddress
from urllib.parse import unquote, urlsplit, urlunsplit

from reconspider.core.normalizer import normalize_url, path_for_scope


def public_address(address):
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if isinstance(ip, ipaddress.IPv6Address) and (ip.sixtofour or ip.teredo):
        return False
    return ip.is_global and not ip.is_multicast and not ip.is_unspecified


def hostname(value):
    value = value.strip().lower().rstrip(".")
    if not value or any(char in value for char in "/:@ "):
        raise ValueError(f"Invalid scope hostname: {value}")
    return value.encode("idna").decode()


class Scope:
    def __init__(self, targets, hosts=(), excludes=(), include_subdomains=False, allow_local=False):
        self.excludes = list(excludes)
        self.allow_local = allow_local
        self.hosts = set()
        self.wildcards = set()
        for value in hosts:
            if value.startswith("*."):
                self.wildcards.add(hostname(value[2:]))
            else:
                self.hosts.add(hostname(value))
        for target in targets:
            host = urlsplit(normalize_url(target)).hostname
            self.hosts.add(host)
            # This explicit switch grants subdomain scope only for provided targets.
            if include_subdomains:
                self.wildcards.add(host)
        if not self.hosts and not self.wildcards:
            raise ValueError("At least one target or scope host is required")

    def check(self, raw, base=None):
        try:
            url = normalize_url(raw, base)
            host = urlsplit(url).hostname
            try:
                literal = ipaddress.ip_address(host)
            except ValueError:
                literal = None
            if literal and not public_address(host) and not self.allow_local:
                return False, "non_public_address"
            if not self.allow_local and (
                host == "localhost" or host.endswith(".localhost") or host.endswith(".local")
            ):
                return False, "non_public_host"
            if host not in self.hosts and not any(
                host.endswith("." + root) for root in self.wildcards
            ):
                return False, "out_of_scope_host"
            path = path_for_scope(url)
            parts = urlsplit(url)
            decoded_url = urlunsplit((parts.scheme, parts.netloc, path, unquote(parts.query), ""))
            if any(
                fnmatch.fnmatchcase(path, pattern)
                or fnmatch.fnmatchcase(url, pattern)
                or fnmatch.fnmatchcase(decoded_url, pattern)
                for pattern in self.excludes
            ):
                return False, "excluded_path"
            return True, "allowed"
        except (ValueError, UnicodeError):
            return False, "invalid_url"
