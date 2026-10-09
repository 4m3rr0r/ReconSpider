"""Explicit snapshot transport to an authenticated HTTPS object-store endpoint."""

import os
from urllib.parse import urlsplit

import httpx


def transfer_snapshot(path, direction):
    url = os.environ.get("RECON_STORAGE_URL", "")
    if urlsplit(url).scheme != "https" or not urlsplit(url).hostname:
        raise ValueError("RECON_STORAGE_URL must be an HTTPS object endpoint")
    headers = {}
    if os.environ.get("RECON_STORAGE_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["RECON_STORAGE_TOKEN"]
    with httpx.Client(
        timeout=60, follow_redirects=False, trust_env=False, headers=headers
    ) as client:
        if direction == "push":
            with open(path, "rb") as stream:
                response = client.put(
                    url, content=stream, headers={"Content-Type": "application/x-ndjson"}
                )
            response.raise_for_status()
        else:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(path, "wb") as stream:
                    for chunk in response.iter_bytes():
                        stream.write(chunk)
