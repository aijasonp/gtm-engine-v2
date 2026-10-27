#!/usr/bin/env python3
"""apify_client.py: run an Apify actor and get its dataset items back over the REST API.

No CLI install, no `apify login`: one POST to run-sync-get-dataset-items with APIFY_TOKEN.
Never raises on HTTP errors; returns None on failure and [] on an empty dataset, so a batch can
log the miss and keep going.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


def get_token() -> str | None:
    tok = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    if tok:
        return tok.strip()
    env_file = Path(os.environ.get("GTM_ENV_FILE") or Path.home() / ".gtm" / ".env").expanduser()
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip().removeprefix("export ")
            for k in ("APIFY_TOKEN=", "APIFY_API_TOKEN="):
                if line.startswith(k):
                    v = line.split("=", 1)[1].split(" #")[0].strip().strip('"').strip("'")
                    if v:
                        return v
    return None


def run_actor(actor_id: str, actor_input: dict, token: str | None = None, timeout: int = 300) -> list[dict] | None:
    """Run `actor_id` (e.g. "harvestapi/linkedin-post-comments") synchronously."""
    token = token or get_token()
    if not token:
        return None
    url = BASE.format(actor=actor_id.replace("/", "~")) + f"?timeout={timeout}"
    req = urllib.request.Request(url, data=json.dumps(actor_input).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout + 30) as r:
            data = json.load(r)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        print(f"  apify {actor_id} failed: {str(e)[:200]}")
        return None
    if isinstance(data, dict):
        data = [data]
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else None
