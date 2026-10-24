#!/usr/bin/env python3
"""Pull ALL HubSpot contacts where `company` (company name text field) is NOT_HAS_PROPERTY.

HubSpot search API caps pagination at 10,000 results per query, so we segment
by createdate windows, recursively splitting any window over 9,000 results.

Output: output/contacts-missing-company-2026-09-23.csv
"""
import csv
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

TOKEN = os.environ["HUBSPOT_TOKEN"]
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
SEARCH_URL = "https://api.hubapi.com/crm/v3/objects/contacts/search"
PROPS = ["firstname", "lastname", "email", "company", "hubspot_owner_id",
         "createdate", "hs_object_id", "associatedcompanyid", "lifecyclestage"]
CAP = 9000  # stay safely under the 10k pagination ceiling


def search(filters, after=None, limit=100):
    body = {"filterGroups": [{"filters": filters}], "properties": PROPS, "limit": limit}
    if after:
        body["after"] = after
    req = urllib.request.Request(SEARCH_URL, data=json.dumps(body).encode(), headers=HEADERS)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                time.sleep(2 ** attempt + 1)
                continue
            raise


def count_in_window(lo_ms, hi_ms):
    filters = [
        {"propertyName": "company", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "createdate", "operator": "GTE", "value": str(lo_ms)},
        {"propertyName": "createdate", "operator": "LT", "value": str(hi_ms)},
    ]
    return search(filters, limit=1)["total"]


def pull_window(lo_ms, hi_ms, out):
    filters = [
        {"propertyName": "company", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "createdate", "operator": "GTE", "value": str(lo_ms)},
        {"propertyName": "createdate", "operator": "LT", "value": str(hi_ms)},
    ]
    after = None
    while True:
        resp = search(filters, after=after)
        out.extend(resp.get("results", []))
        paging = resp.get("paging", {}).get("next", {})
        after = paging.get("after")
        if not after:
            break


def walk(lo_ms, hi_ms, out):
    total = count_in_window(lo_ms, hi_ms)
    if total == 0:
        return
    if total > CAP:
        mid = (lo_ms + hi_ms) // 2
        walk(lo_ms, mid, out)
        walk(mid, hi_ms, out)
        return
    print(f"  window {datetime.fromtimestamp(lo_ms/1000, timezone.utc):%Y-%m-%d} -> "
          f"{datetime.fromtimestamp(hi_ms/1000, timezone.utc):%Y-%m-%d}: {total}", flush=True)
    pull_window(lo_ms, hi_ms, out)


def main():
    # Global range: 2020-01-01 through now (HubSpot data predates nothing relevant)
    lo = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    hi = int(datetime.now(timezone.utc).timestamp() * 1000) + 1000
    results = []
    walk(lo, hi, results)
    # Dedupe by object id (window boundaries can overlap on ties)
    seen = {}
    for r in results:
        seen[r["id"]] = r
    rows = list(seen.values())
    print(f"TOTAL pulled (deduped): {len(rows)}")

    os.makedirs("output", exist_ok=True)
    path = "output/contacts-missing-company-2026-09-23.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["contact_id", "firstname", "lastname", "email", "company",
                    "associatedcompanyid", "lifecyclestage", "hubspot_owner_id", "createdate"])
        for r in rows:
            p = r.get("properties", {})
            w.writerow([r["id"], p.get("firstname") or "", p.get("lastname") or "",
                        p.get("email") or "", p.get("company") or "",
                        p.get("associatedcompanyid") or "", p.get("lifecyclestage") or "",
                        p.get("hubspot_owner_id") or "", p.get("createdate") or ""])
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
