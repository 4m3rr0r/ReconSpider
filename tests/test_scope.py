import pytest
from twisted.internet.address import IPv4Address, IPv6Address

from reconspider.core.resolver import SafeReceiver, SafeResolver
from reconspider.core.scope import Scope, public_address


@pytest.mark.parametrize(
    "url,allowed",
    [
        ("https://example.com/", True),
        ("https://sub.example.com/", False),
        ("https://example.com.evil.org/", False),
        ("https://evil-example.com/", False),
        ("https://example.com/private/a", False),
        ("https://example.com/%70rivate/a", False),
        ("https://example.com/x/../private/a", False),
        ("https://example.com@evil.org/", False),
        ("file:///etc/passwd", False),
        ("https://example.com./", True),
    ],
)
def test_scope(url, allowed):
    assert Scope(["https://example.com"], excludes=["/private*"]).check(url)[0] == allowed


def test_subdomains_require_explicit_grant():
    scope = Scope(["https://example.com"], hosts=["*.authorized.example.com"])
    assert scope.check("https://a.authorized.example.com")[0]
    assert not scope.check("https://authorized.example.com")[0]
    assert not scope.check("https://other.example.com")[0]
    assert Scope(["https://example.com"], include_subdomains=True).check(
        "https://other.example.com"
    )[0]


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "0.0.0.0",
        "10.0.0.1",
        "169.254.169.254",
        "::1",
        "fc00::1",
        "fe80::1",
        "::ffff:127.0.0.1",
        "224.0.0.1",
        "100.64.0.1",
    ],
)
def test_ssrf(host):
    assert not public_address(host)


class Receiver:
    def __init__(self):
        self.addresses = []
        self.complete = False

    def resolutionBegan(self, resolution):
        pass

    def addressResolved(self, address):
        self.addresses.append(address.host)

    def resolutionComplete(self):
        self.complete = True


def test_mixed_dns_answer_is_rejected_before_connection():
    receiver = Receiver()
    guard = SafeReceiver(receiver)
    guard.resolutionBegan(None)
    guard.addressResolved(IPv4Address("TCP", "8.8.8.8", 443))
    assert receiver.addresses == []
    guard.addressResolved(IPv6Address("TCP", "::1", 443))
    guard.resolutionComplete()
    assert receiver.complete and receiver.addresses == []


def test_rebinding_on_second_connection():
    class DNS:
        count = 0

        def resolveHostName(self, receiver, *args):
            self.count += 1
            receiver.resolutionBegan(None)
            receiver.addressResolved(
                IPv4Address("TCP", "8.8.8.8" if self.count == 1 else "127.0.0.1", 443)
            )
            receiver.resolutionComplete()

    class Reactor:
        nameResolver = DNS()

    resolver = SafeResolver(Reactor())
    first, second = Receiver(), Receiver()
    resolver.resolveHostName(first, "example.com")
    resolver.resolveHostName(second, "example.com")
    assert first.addresses == ["8.8.8.8"] and second.addresses == []
