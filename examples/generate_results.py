"""Generate reviewable example artifacts using only the local fixture."""

import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from local_app import Handler


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        directory = Path(__file__).resolve().parent / "results"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "reconspider.cli",
                "crawl",
                "--target",
                "http://127.0.0.1:8000",
                "--allow-local",
                "--rate-limit",
                "100",
                "--max-pages",
                "30",
                "--output",
                str(directory),
            ],
            check=True,
        )
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
