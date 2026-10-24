#!/usr/bin/env python3
"""Resolve HubSpot owner IDs to human names + emails.

HubSpot stores record ownership as a bare numeric `hubspot_owner_id`
(e.g. "10000001"). This module fetches the full owner directory (active
AND archived) once per process, caches it, and exposes a resolver so
lookups can show "Pat Example" instead of "(10000001)".

Archived owners matter: departed reps (e.g. Pat Example) still own
records, and a bare ID with no name is exactly the confusion this fixes.

Usage:
    from hubspot_owners import OwnerResolver
    resolver = OwnerResolver(token)
    print(resolver.name("10000001"))   # "Pat Example"
    print(resolver.label("10000001"))  # "Pat Example (pat@example.com)"
    print(resolver.label("99999999"))  # "Owner 99999999 (unknown)"
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

API_BASE = "https://api.hubapi.com"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Cache file so repeated lookups across processes don't re-hit the API.
# Keyed by token hash so different creds don't collide.
CACHE_DIR = os.path.expanduser("~/.cache/hubspot")
CACHE_TTL_SECONDS = 6 * 3600  # refresh every 6h


class OwnerResolver:
    def __init__(self, token: str, *, timeout: int = 30) -> None:
        self.token = token
        self.timeout = timeout
        self._by_id: Optional[Dict[str, Dict[str, Any]]] = None

    # --- HTTP ------------------------------------------------------------

    def _request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from urllib.parse import urlencode

        url = API_BASE + path
        if params:
            query = urlencode({k: v for k, v in params.items() if v is not None})
            if query:
                url += f"?{query}"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        for attempt in range(5):
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                status = getattr(e, "code", None)
                if status in RETRYABLE_STATUS and attempt < 4:
                    time.sleep(min(2 ** attempt, 15))
                    continue
                raise RuntimeError(f"HubSpot owners error {status} on {path}")
            except urllib.error.URLError as e:
                if attempt == 4:
                    raise RuntimeError(f"Network error on {path}: {e}")
                time.sleep(min(2 ** attempt, 10))
        raise RuntimeError(f"HubSpot owners request failed: {path}")

    def _fetch_all(self) -> Dict[str, Dict[str, Any]]:
        """Fetch active + archived owners, keyed by id."""
        by_id: Dict[str, Dict[str, Any]] = {}
        for archived in (False, True):
            after: Optional[str] = None
            while True:
                params = {"limit": "100", "archived": "true" if archived else "false"}
                if after:
                    params["after"] = after
                res = self._request("/crm/v3/owners", params)
                for owner in res.get("results", []) or []:
                    oid = str(owner.get("id"))
                    if oid:
                        by_id[oid] = owner
                nxt = (res.get("paging") or {}).get("next")
                if not nxt:
                    break
                after = str(nxt.get("after"))
        return by_id

    # --- Cache -----------------------------------------------------------

    def _cache_path(self) -> str:
        os.makedirs(CACHE_DIR, exist_ok=True)
        digest = str(abs(hash(self.token)))  # not security, just cache keying
        return os.path.join(CACHE_DIR, f"owners-{digest}.json")

    def _load_cached(self) -> Optional[Dict[str, Dict[str, Any]]]:
        path = self._cache_path()
        try:
            if os.path.getmtime(path) < time.time() - CACHE_TTL_SECONDS:
                return None
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None

    def _save_cache(self, by_id: Dict[str, Dict[str, Any]]) -> None:
        try:
            with open(self._cache_path(), "w", encoding="utf-8") as fh:
                json.dump(by_id, fh)
        except Exception:
            pass  # cache is best-effort

    # --- Public API ------------------------------------------------------

    def owners(self) -> Dict[str, Dict[str, Any]]:
        """Return the owner map (id -> owner object), cached."""
        if self._by_id is None:
            self._by_id = self._load_cached()
            if self._by_id is None:
                self._by_id = self._fetch_all()
                self._save_cache(self._by_id)
        return self._by_id

    def get(self, owner_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not owner_id:
            return None
        return self.owners().get(str(owner_id))

    def name(self, owner_id: Optional[str]) -> Optional[str]:
        owner = self.get(owner_id)
        if not owner:
            return None
        first = (owner.get("firstName") or "").strip()
        last = (owner.get("lastName") or "").strip()
        return (first + " " + last).strip() or None

    def email(self, owner_id: Optional[str]) -> Optional[str]:
        owner = self.get(owner_id)
        if not owner:
            return None
        return (owner.get("email") or "").strip() or None

    def label(self, owner_id: Optional[str]) -> str:
        """Human-friendly label: 'Pat Example (pat@example.com)' or fallback."""
        if not owner_id:
            return "Unassigned"
        name = self.name(owner_id)
        email = self.email(owner_id)
        if name and email:
            return f"{name} ({email})"
        if name:
            return name
        if email:
            return email
        return f"Owner {owner_id} (unknown)"


def load_token() -> str:
    token = os.environ.get("HUBSPOT_API_TOKEN") or os.environ.get("HUBSPOT_API_KEY")
    if not token:
        raise RuntimeError("HUBSPOT_API_TOKEN env var is required")
    return token.strip()


if __name__ == "__main__":
    import sys

    resolver = OwnerResolver(load_token())
    ids = sys.argv[1:] or ["10000001"]
    for oid in ids:
        print(f"{oid} -> {resolver.label(oid)}")
