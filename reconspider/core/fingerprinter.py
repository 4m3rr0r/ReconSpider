from hashlib import sha256

from reconspider.core.normalizer import normalize_url


class ExactFingerprinter:
    def fingerprint(self, request):
        # Scrapy's default sorts query pairs. Keep routing-sensitive order and duplicates.
        return sha256(
            request.method.encode()
            + b"\0"
            + normalize_url(request.url).encode()
            + b"\0"
            + request.body
        ).digest()
