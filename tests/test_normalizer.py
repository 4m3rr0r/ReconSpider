import scrapy

from reconspider.core.fingerprinter import ExactFingerprinter
from reconspider.core.normalizer import fingerprints, normalize_url


def test_normalization():
    assert (
        normalize_url("HTTPS://EXAMPLE.COM:443/a/../b?x=1&x=2#frag")
        == "https://example.com/b?x=1&x=2"
    )
    assert normalize_url("../x", "https://example.com/a/b") == "https://example.com/x"
    assert normalize_url("//EXAMPLE.com:80", "http://other.com") == "http://example.com/"
    assert normalize_url("https://example.com/%7efoo/%2f") == "https://example.com/~foo/%2F"
    assert normalize_url("https://example.com/a//b") == "https://example.com/a//b"


def test_fingerprints_preserve_values_and_duplicate_keys():
    one, two = "https://example.com/?id=1&id=2", "https://example.com/?id=2&id=1"
    assert normalize_url(one) != normalize_url(two)
    fingerprinter = ExactFingerprinter()
    assert fingerprinter.fingerprint(scrapy.Request(one)) != fingerprinter.fingerprint(
        scrapy.Request(two)
    )
    assert fingerprints(one)["parameter_fingerprint"] == "https://example.com/?id=VALUE&id=VALUE"
