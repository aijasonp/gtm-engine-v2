#!/usr/bin/env python3
"""
No-scrape freebie: contacts missing `company` text field but already linked to a
company record (associatedcompanyid set). Batch-read the linked companies, map
names back. Sheet-first: results to a new tab. NO HubSpot writes.
"""
import csv, json, os, subprocess, sys, time, urllib.request, urllib.error
from urllib.parse import quote

import requests

WS = os.path.expanduser("~/.openclaw/workspace")
OUT = os.path.join(WS, "output", "company-cleanup")
SHEET = "REDACTED_GOOGLE_ID"
GWSG = os.path.expanduser("~/.local/bin/gwsg")
TAB = "Linked Contacts - Company Names"

sys.path.insert(0, os.path.join(WS, "scripts", "company-cleanup"))
import scrape_free_data as sfd  # quarter_windows, hs_search_windowed

HUBSPOT_TOKEN = None
for line in open(os.path.expanduser("~/.openclaw/.env")):
    if line.startswith("HUBSPOT_TOKEN="):
        HUBSPOT_TOKEN = line.strip().split("=", 1)[1]
assert HUBSPOT_TOKEN
HS = "https://api.hubapi.com"
HDR = {"Authorization": f"Bearer {HUBSPOT_TOKEN}"}

GREEN = {"red": 0.85, "green": 0.95, "blue": 0.85}
HEADER_BG = {"red": 0.15, "green": 0.15, "blue": 0.15}


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def get_token():
    r = subprocess.run([GWSG, "auth", "token"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"auth token failed: {r.stderr}")
    return r.stdout.strip()


def sheets_api(method, path, body=None):
    token = get_token()
    req = urllib.request.Request(
        f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:500]}") from e


def pull_linked_contacts():
    base = [
        {"propertyName": "company", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "associatedcompanyid", "operator": "HAS_PROPERTY"},
    ]
    props = ["email", "company", "associatedcompanyid", "lifecyclestage", "createdate"]
    recs = []
    windows = sfd.quarter_windows()
    for i, (s, e) in enumerate(windows):
        chunk = sfd.hs_search_windowed("contacts", base, props, s, e)
        recs.extend(chunk)
        log(f"  window {i+1}/{len(windows)}: +{len(chunk)} (total {len(recs)})")
    seen, out = set(), []
    for r in recs:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        p = r["properties"]
        cid = (p.get("associatedcompanyid") or "").strip()
        if not cid:
            continue
        out.append({
            "id": r["id"],
            "email": p.get("email") or "",
            "associatedcompanyid": cid,
            "lifecyclestage": p.get("lifecyclestage") or "",
        })
    return out


def batch_read_company_names(ids):
    names = {}
    ids = list(dict.fromkeys(ids))
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        r = requests.post(
            f"{HS}/crm/v3/objects/companies/batch/read",
            headers={**HDR, "Content-Type": "application/json"},
            json={"properties": ["name", "domain"], "inputs": [{"id": x} for x in chunk]},
            timeout=60,
        )
        if r.status_code != 200:
            log(f"  batch read HTTP {r.status_code}: {r.text[:200]}")
            continue
        for res in r.json().get("results", []):
            p = res.get("properties", {})
            names[res["id"]] = {"name": p.get("name") or "", "domain": p.get("domain") or ""}
        time.sleep(0.15)
    return names


def main():
    t0 = time.time()
    log("=== linked contacts pass start ===")
    contacts = pull_linked_contacts()
    log(f"{len(contacts)} contacts missing company text but linked to a company")

    company_ids = [c["associatedcompanyid"] for c in contacts]
    log(f"batch-reading {len(set(company_ids))} unique companies...")
    names = batch_read_company_names(company_ids)
    log(f"got names for {len(names)} companies")

    rows = []
    for c in contacts:
        co = names.get(c["associatedcompanyid"], {})
        cname = co.get("name", "")
        rows.append({
            "id": c["id"], "email": c["email"],
            "company_id": c["associatedcompanyid"],
            "company_name": cname, "company_domain": co.get("domain", ""),
            "lifecyclestage": c["lifecyclestage"],
            "status": "recovered" if cname else "company-record-has-no-name",
        })
    rows.sort(key=lambda r: (0 if r["status"] == "recovered" else 1, r["company_name"], r["email"]))

    csv_path = os.path.join(OUT, "linked_contacts_company_names.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "email", "company_id", "company_name", "company_domain", "lifecyclestage", "status"])
        for r in rows:
            w.writerow([r["id"], r["email"], r["company_id"], r["company_name"],
                        r["company_domain"], r["lifecyclestage"], r["status"]])
    rec = sum(1 for r in rows if r["status"] == "recovered")
    log(f"{rec}/{len(rows)} contacts mapped to a company name in {(time.time()-t0)/60:.1f}m")

    # --- write tab ---
    n = len(rows)
    sheet_id = None
    try:
        j = sheets_api("POST", ":batchUpdate", {"requests": [
            {"addSheet": {"properties": {"title": TAB, "gridProperties": {"rowCount": n + 60, "columnCount": 7}}}}]})
        sheet_id = j["replies"][0]["addSheet"]["properties"]["sheetId"]
        log(f"created tab sheetId={sheet_id}")
    except Exception as e:
        if "already exists" in str(e):
            j = sheets_api("GET", "?fields=sheets.properties")
            for s in j["sheets"]:
                if s["properties"]["title"] == TAB:
                    sheet_id = s["properties"]["sheetId"]
            sheets_api("POST", ":batchUpdate", {"requests": [{"updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"rowCount": n + 60}},
                "fields": "gridProperties.rowCount"}}]})
            log(f"tab exists sheetId={sheet_id}, resized")
        else:
            raise

    header = ["HubSpot ID", "Email", "Company ID", "Company Name", "Company Domain", "Lifecycle", "Result"]
    values = [header] + [[r["id"], r["email"], r["company_id"], r["company_name"],
                          r["company_domain"], r["lifecyclestage"],
                          "RECOVERED" if r["status"] == "recovered" else "COMPANY RECORD HAS NO NAME"]
                         for r in rows]
    sheets_api("PUT", f"/values/{quote(TAB + '!A1', safe='')}?valueInputOption=RAW",
               {"range": f"{TAB}!A1", "majorDimension": "ROWS", "values": values})
    log(f"wrote {len(values)} rows")

    reqs = [
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": 7},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_BG,
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)"}},
    ]
    if rec:
        reqs.append({"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 1 + rec,
                      "startColumnIndex": 0, "endColumnIndex": 7},
            "cell": {"userEnteredFormat": {"backgroundColor": GREEN, "textFormat": {"bold": True}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)"}})
    sheets_api("POST", ":batchUpdate", {"requests": reqs})
    log(f"formatted: {rec} recovered rows highlighted")
    print(json.dumps({"contacts": n, "recovered": rec, "sheetId": sheet_id}))


if __name__ == "__main__":
    main()
