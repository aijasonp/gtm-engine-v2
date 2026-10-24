#!/usr/bin/env python3
"""Rewrite the TLDR Summary tab: keep the audit block, prepend a results block (updated 2026-09-25)."""
import json, os, subprocess, urllib.request, urllib.error
from urllib.parse import quote

SHEET = "REDACTED_GOOGLE_ID"
GWSG = os.path.expanduser("~/.local/bin/gwsg")
TAB = "TLDR Summary"
SHEET_ID = 0000000

GREEN = {"red": 0.85, "green": 0.95, "blue": 0.85}
ORANGE = {"red": 0.98, "green": 0.88, "blue": 0.78}
HEADER_BG = {"red": 0.15, "green": 0.15, "blue": 0.15}


def get_token():
    r = subprocess.run([GWSG, "auth", "token"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    return r.stdout.strip()


def api(method, path, body=None):
    req = urllib.request.Request(
        f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:500]}") from e


ROWS = [
    ["MISSING COMPANY DATA - AUDIT + RECOVERY RESULTS (updated 2026-09-25)"],
    [],
    ["WHAT WAS RECOVERED (this week's passes)"],
    ["  Company names recovered (805 nameless companies)", "213", "111 high / 67 medium / 35 low confidence"],
    ["  Industries filled (1,680 companies missing industry)", "645", "Jev AI classified into HubSpot picklist; median confidence 0.93+"],
    ["  Contact company names recovered (1,892 corporate-email contacts)", "102", "62 high / 28 medium / 12 low confidence"],
    ["  Linked-contact backfill (1,849 contacts already tied to a company)", "2", "the other 1,847 link to the SAME 805 nameless companies - covered by the company pass above"],
    ["  TOTAL records with data recovered", "960", "213 + 645 + 102 (deduped by record)"],
    [],
    ["WHERE THE DATA LIVES (tabs on this sheet, recovered rows highlighted green + sorted to top)"],
    ["  'Scrape Pass - Companies'", "807 rows", "company name recovery results"],
    ["  'Industry Pass - Companies'", "1,680 rows", "industry classification results (NEW 2026-09-25)"],
    ["  'Scrape Pass - Contacts'", "1,963 rows", "contact company-name recovery results"],
    ["  'Scrape Pass - Domains'", "864 rows", "raw per-domain scrape data + meta descriptions"],
    ["  'Linked Contacts - Company Names'", "1,849 rows", "associatedcompanyid backfill check (NEW 2026-09-25)"],
    [],
    ["WHY NOT MORE (the honest ceiling of free recovery)"],
    ["  Dead domains", "531", "site gone / DNS dead / SSL broken / timeout - the company itself appears defunct or the domain lapsed"],
    ["  Bot-blocked (Cloudflare/Akamai/LinkedIn 999)", "48+", "CDN blocks datacenter IPs; needs browser-grade scraping (Lightpanda) or paid enrichment"],
    ["  Personal-email contacts", "19,319", "gmail/yahoo/hotmail signups carry zero company signal - no free method can recover these"],
    ["  Site up but no usable name", "37+", "JS-rendered pages, parked domains, junk pages"],
    ["  Unmappable remainder", "~17.5K", "subscriber-lifecycle personal emails + no-email records: unrecoverable without paid data"],
    [],
    ["NOT DONE YET"],
    ["  HubSpot writes: NOTHING has been written to HubSpot - all results are on this sheet for your review first"],
    ["  Browser-grade re-scrape of the 48+ bot-blocked domains (Lightpanda stack)"],
    ["  Your call: which recovered rows get written back to HubSpot, and whether paid enrichment is worth it for the ~17.5K personal-email records"],
    [],
    ["─────────────────────────────────────────────"],
    ["ORIGINAL AUDIT (2026-09-23, corrected)"],
    [],
    ["OBJECT 1: COMPANIES missing `name`", "805"],
    ["  - all 805 have domain/website (recoverable via enrichment)"],
    ["  - see 'All Companies' tab"],
    [],
    ["OBJECT 2: CONTACTS missing `company` name", "22,830"],
    ["  - total across both objects = 23,635"],
    ["  - see 'Contacts Missing Company' tab"],
    [],
    ["CONTACT BREAKDOWN"],
    ["  with email address", "21,424"],
    ["  ... gmail.com (personal, no company signal)", "18,331"],
    ["  ... other free/ISP mail (yahoo/hotmail/outlook/icloud/etc)", "988"],
    ["  ... corporate-looking domains (recoverable)", "~2,105"],
    ["  no email at all", "1,406"],
    ["  already linked to a company record (associatedcompanyid set)", "1,848"],
    [],
    ["CONTACT LIFECYCLE STAGE"],
    ["  subscriber (newsletter/blog signups - mostly personal emails)", "18,702"],
    ["  lead", "4,024"],
    ["  salesqualifiedlead", "72"],
    ["  marketingqualifiedlead", "30"],
    [],
    ["TOP CONTACT OWNERS"],
    ["  Former/deactivated owner (0000000)", "13,680"],
    ["  Unassigned", "4,087"],
    ["  {{TEAMMATE_6}}", "2,582"],
    ["  Jason Polanco", "1,583"],
    ["  {{TEAMMATE_5}} ", "785"],
    ["  Former/deactivated owner (0000000)", "43"],
    ["  Former/deactivated owner (0000000)", "20"],
    ["  {{AE_6}}", "20"],
    ["  {{AE_1}}", "8"],
    ["  {{AE_4}}", "7"],
    [],
    ["CONTACTS BY CREATE YEAR"],
    ["  2023", "7,275"],
    ["  2024", "8,477"],
    ["  2025", "5,662"],
    ["  2026", "1,416"],
    [],
    ["ROOT CAUSE"],
    ["The 805 nameless companies were only the tip. 22,830 contacts have no company name - 28% of all 81,309 contacts."],
    ["Newsletter/event imports. 18.7K are 'subscriber' lifecycle (blog/newsletter signups with personal gmail) - HubSpot never got a company."],
    ["~13.7K sit under one deactivated owner id (0000000) = bulk import legacy."],
    ["The 4,026 leads + SQLs + MQLs with corporate domains are the fix-first slice - those are active pipeline with no account context."],
]


def main():
    n = len(ROWS)
    api("POST", ":batchUpdate", {"requests": [
        {"updateSheetProperties": {
            "properties": {"sheetId": SHEET_ID, "gridProperties": {"rowCount": n + 20}},
            "fields": "gridProperties.rowCount"}}]})
    api("PUT", f"/values/{quote(TAB + '!A1', safe='')}?valueInputOption=RAW",
        {"range": f"{TAB}!A1", "majorDimension": "ROWS", "values": ROWS})
    print(f"wrote {n} rows", flush=True)

    reqs = [
        # title row
        {"repeatCell": {
            "range": {"sheetId": SHEET_ID, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_BG,
                "textFormat": {"bold": True, "fontSize": 12,
                               "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)"}},
        # section headers (rows 2, 9, 17, 26 zero-indexed)
        *[{"repeatCell": {
            "range": {"sheetId": SHEET_ID, "startRowIndex": r, "endRowIndex": r + 1,
                      "startColumnIndex": 0, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {"backgroundColor": ORANGE, "textFormat": {"bold": True}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)"}} for r in (2, 9, 17, 26)],
        # total row highlight (row 7 zero-indexed)
        {"repeatCell": {
            "range": {"sheetId": SHEET_ID, "startRowIndex": 7, "endRowIndex": 8,
                      "startColumnIndex": 0, "endColumnIndex": 3},
            "cell": {"userEnteredFormat": {"backgroundColor": GREEN, "textFormat": {"bold": True}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)"}},
    ]
    api("POST", ":batchUpdate", {"requests": reqs})
    print("formatted", flush=True)


if __name__ == "__main__":
    main()
