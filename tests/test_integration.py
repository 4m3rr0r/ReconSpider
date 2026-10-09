import json
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer

from examples.local_app import Handler


def test_complete_local_crawl(tmp_path):
    hits = []

    class RecordingHandler(Handler):
        def do_GET(self):
            hits.append(self.path)
            super().do_GET()

    server = ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "reconspider.cli",
                "crawl",
                "--target",
                f"http://127.0.0.1:{server.server_port}",
                "--allow-local",
                "--rate-limit",
                "100",
                "--max-pages",
                "30",
                "--output",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
        assert result.returncode == 0, result.stderr
        records = [
            json.loads(line) for line in (tmp_path / "crawl_results.jsonl").read_text().splitlines()
        ]
        assert any(r.get("source") == "javascript" for r in records)
        assert any(r.get("source") == "http_redirect" for r in records)
        assert any(r.get("kind") == "form" for r in records)
        assert not any(path == "/blocked" for path in hits)
        assert not any("{" in path for path in hits)
        assert (tmp_path / "report.html").exists()
        assert len(hits) <= 30
    finally:
        server.shutdown()
        server.server_close()


def test_private_dns_answer_cannot_reach_fixture(tmp_path):
    hits = []

    class RecordingHandler(Handler):
        def do_GET(self):
            hits.append(self.path)
            super().do_GET()

    server = ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    script = """
import socket
import sys
from reconspider.cli import main
original = socket.getaddrinfo
socket.gethostbyname = lambda name: '127.0.0.1'
socket.getaddrinfo = lambda host, *args, **kwargs: original('127.0.0.1', *args, **kwargs)
sys.exit(main(sys.argv[1:]))
"""
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                "crawl",
                "--target",
                f"http://rebind.example.invalid:{server.server_port}",
                "--rate-limit",
                "100",
                "--max-pages",
                "10",
                "--output",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
        assert result.returncode == 0, result.stderr
        assert not hits
        records = [
            json.loads(line) for line in (tmp_path / "crawl_results.jsonl").read_text().splitlines()
        ]
        assert any(r.get("kind") == "error" for r in records)
        assert not any(r.get("kind") == "response" for r in records)
    finally:
        server.shutdown()
        server.server_close()
