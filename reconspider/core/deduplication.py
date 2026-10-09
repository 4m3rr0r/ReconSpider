from reconspider.core.normalizer import fingerprints, normalize_url


class URLDeduplicator:
    def __init__(self):
        self.seen = set()

    def add(self, raw, base=None):
        url = normalize_url(raw, base)
        fresh = url not in self.seen
        self.seen.add(url)
        return url, fresh

    @staticmethod
    def pattern(url):
        return fingerprints(url)["parameter_fingerprint"]
