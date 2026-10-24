#!/usr/bin/env python3
"""Export all HubSpot contacts with NO associated company to CSV.

Uses the v3 LIST endpoint (GET /crm/v3/objects/contacts) which paginates past
the search API's 10k 'after' cap, then filters client-side for contacts whose
companies association is empty (and associatedcompanyid is null).

Stdlib only: urllib, json, csv, time, os, sys.
"""

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_TOKEN = os.environ.get("HUBSPOT_API_TOKEN")
if not API_TOKEN:
    sys.exit("FATAL: HUBSPOT_API_TOKEN env var not set")

BASE = "https://api.hubapi.com/crm/v3/objects/contacts"
PROPERTIES = [
    "firstname", "lastname", "email", "jobtitle", "phone", "mobilephone",
    "city", "state", "country", "hs_lead_status", "lifecyclestage",
    "createdate", "lastmodifieddate", "hs_analytics_source",
    "associatedcompanyid",
]

CSV_COLUMNS = [
    "hubspot_id", "firstname", "lastname", "email", "jobtitle", "phone",
    "mobilephone", "city", "state", "country", "lifecyclestage",
    "hs_lead_status", "createdate", "lastmodifieddate", "hs_analytics_source",
]

OUT_CSV = os.path.expanduser("~/.openclaw/workspace/output/contacts-no-company-2026-09-21.csv")
OUT_STATS = os.path.expanduser("~/.openclaw/workspace/output/contacts-no-company-2026-09-21-stats.txt")


def api_get(url):
    """GET with retry + exponential backoff on 429/5xx. Returns parsed JSON."""
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + API_TOKEN,
        "Accept": "application/json",
    })
    for attempt in range(6):  # initial + 5 retries
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                wait = (2 ** attempt) + (attempt * 2)
                print(f"  HTTP {e.code} on attempt {attempt+1}; backing off {wait}s",
                      flush=True)
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            wait = (2 ** attempt) + (attempt * 2)
            print(f"  URLError {e} on attempt {attempt+1}; backing off {wait}s",
                  flush=True)
            time.sleep(wait)
            continue
    raise RuntimeError(f"Gave up after retries on {url}")


def prop(contact, name):
    """Return property value or '' for a contact."""
    props = contact.get("properties") or {}
    val = props.get(name)
    return val if val is not None else ""


def has_no_company(contact):
    """True if contact has no associated company."""
    # Check associations first (authoritative for the list endpoint)
    assoc = contact.get("associations") or {}
    companies = (assoc.get("companies") or {}).get("results") or []
    if companies:
        return False
    # Double-check associatedcompanyid is null/empty
    acid = prop(contact, "associatedcompanyid")
    if acid:
        return False
    return True


def main():
    print("Starting export of HubSpot contacts with no associated company...",
          flush=True)

    rows = []
    url = (BASE + "?limit=100&archived=false&properties="
           + urllib.parse.quote(",".join(PROPERTIES))
           + "&associations=companies")

    total_seen = 0
    kept = 0
    page = 0
    while url:
        page += 1
        data = api_get(url)
        results = data.get("results") or []
        total_seen += len(results)

        for c in results:
            if has_no_company(c):
                rows.append(c)
                kept += 1

        if total_seen % 1000 < len(results) or (total_seen // 1000) > ((total_seen - len(results)) // 1000):
            print(f"  scanned {total_seen} contacts, kept {kept} (page {page})",
                  flush=True)

        paging = data.get("paging") or {}
        nxt = (paging.get("next") or {}).get("after")
        if nxt:
            url = (BASE + "?limit=100&archived=false&properties="
                   + urllib.parse.quote(",".join(PROPERTIES))
                   + "&associations=companies&after=" + str(nxt))
        else:
            url = None

    print(f"Done scanning. Total scanned: {total_seen}, kept (no company): {kept}",
          flush=True)

    # SANITY CHECK: search endpoint said 26,314. Client-side filter should be close.
    if kept < 20000 or kept > 40000:
        print(f"FATAL SANITY CHECK FAILED: expected ~26,314 contacts with no "
              f"company, but client-side filter produced {kept}. Aborting without "
              f"writing CSV.", flush=True)
        sys.exit(2)

    # Write CSV
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for c in rows:
            writer.writerow({col: prop(c, col) for col in CSV_COLUMNS})

    # Stats
    with_email = sum(1 for c in rows if prop(c, "email"))
    with_phone = sum(1 for c in rows if prop(c, "phone") or prop(c, "mobilephone"))
    with_jobtitle = sum(1 for c in rows if prop(c, "jobtitle"))
    with_city_state = sum(1 for c in rows if prop(c, "city") and prop(c, "state"))

    stats_lines = [
        f"total_contacts_exported: {kept}",
        f"with_email: {with_email}",
        f"with_phone: {with_phone}",
        f"with_jobtitle: {with_jobtitle}",
        f"with_city_and_state: {with_city_state}",
    ]
    with open(OUT_STATS, "w", encoding="utf-8") as f:
        f.write("\n".join(stats_lines) + "\n")

    print("Stats:")
    for line in stats_lines:
        print("  " + line)
    print(f"CSV written to {OUT_CSV}")
    print(f"Stats written to {OUT_STATS}")


if __name__ == "__main__":
    main()
