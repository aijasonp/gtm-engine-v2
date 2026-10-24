#!/usr/bin/env python3
"""
Rework the 3 scrape-pass tabs on the audit sheet (Jason feedback 2026-09-25):
  - Sort recovered rows first (confidence desc), failures last
  - Add a plain-English "Result" column (RECOVERED / DEAD DOMAIN / BOT BLOCKED / NO DATA / FILTERED)
  - Bold + light-green fill on recovered rows
  - Fix mojibake rows (139.com style latin1-as-utf8 titles) where possible

Uses Sheets API via gwsg CLI. No HubSpot writes.
"""
import csv, json, os, subprocess, sys, time, urllib.request, urllib.error
from urllib.parse import quote

WS = os.path.expanduser("~/.openclaw/workspace")
OUT = os.path.join(WS, "output", "company-cleanup")
SHEET = "REDACTED_GOOGLE_ID"
GWSG = os.path.expanduser("~/.local/bin/gwsg")

GREEN = {"red": 0.85, "green": 0.95, "blue": 0.85}
HEADER_BG = {"red": 0.15, "green": 0.15, "blue": 0.15}


def get_token():
    r = subprocess.run([GWSG, "auth", "token"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"auth token failed: {r.stderr}")
    return r.stdout.strip()


def api(method, path, body=None):
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


def gwsg_batch(requests_list):
    return api("POST", ":batchUpdate", {"requests": requests_list})


def gwsg_update_values(range_a1, values):
    body = {"range": range_a1, "majorDimension": "ROWS", "values": values}
    return api("PUT", f"/values/{quote(range_a1, safe='')}?valueInputOption=RAW", body)


def fix_mojibake(s):
    """Repair latin1-decoded-as-utf8 titles when they clearly aren't Latin-script text."""
    if not s:
        return s
    try:
        repaired = s.encode("latin1").decode("utf-8")
        # keep repair only if it yields fewer replacement chars / mojibake markers
        if repaired.count("�") < s.count("�") and "å\x9b" not in repaired:
            return repaired
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return s


def result_label(source, name):
    if name:
        return "RECOVERED"
    if not source:
        return "NO DATA"
    if source.startswith("unreachable:ConnectionError") or "ConnectTimeout" in source or "ReadTimeout" in source or "SSLError" in source:
        return "DEAD DOMAIN / UNREACHABLE"
    if "403" in source or "401" in source or "999" in source or "429" in source:
        return "BOT BLOCKED"
    if source.startswith("unreachable:404"):
        return "DEAD DOMAIN (404)"
    if source == "no-signal":
        return "SITE UP, NO NAME FOUND"
    if source in ("freemail-filtered", "freemail-brand-filtered"):
        return "PERSONAL EMAIL (skipped)"
    if source == "junk-filtered":
        return "PARKED/JUNK PAGE"
    if source.startswith("unreachable"):
        return "UNREACHABLE"
    return "NO DATA"


def rank(source, name, conf):
    if name:
        order = {"high": 0, "medium": 1, "low": 2}.get(conf, 3)
        return (0, order)
    lbl = result_label(source, name)
    group = {
        "SITE UP, NO NAME FOUND": 1,
        "BOT BLOCKED": 2,
        "PARKED/JUNK PAGE": 3,
        "PERSONAL EMAIL (skipped)": 4,
        "DEAD DOMAIN (404)": 5,
        "DEAD DOMAIN / UNREACHABLE": 6,
        "UNREACHABLE": 6,
    }.get(lbl, 7)
    return (group, 0)


def load_rows(path, kind):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        name = fix_mojibake(r.get("recovered_name", "").strip())
        src = r.get("source", "")
        conf = r.get("confidence", "")
        out.append((r, name, src, conf))
    out.sort(key=lambda t: (rank(t[2], t[1], t[3]), t[0].get("domain", "")))
    return out


def rewrite_tab(tab, sheet_id, header, rows, col_count):
    n = len(rows)
    # 1. ensure grid is big enough
    gwsg_batch([{
        "updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "gridProperties": {"rowCount": n + 60}},
            "fields": "gridProperties.rowCount",
        }
    }])
    # 2. write values
    values = [header] + rows
    gwsg_update_values(f"'{tab}'!A1", values)
    # 3. clear any leftover rows below
    if n + 61 <= 25000:
        gwsg_batch([{
            "updateCells": {
                "range": {"sheetId": sheet_id,
                          "startRowIndex": n + 1, "endRowIndex": n + 60,
                          "startColumnIndex": 0, "endColumnIndex": col_count},
                "fields": "userEnteredValue",
            }
        }])
    # 4. formatting: header + recovered highlight
    recovered_count = sum(1 for r in rows if r[-1] == "RECOVERED")
    reqs = [
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": col_count},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_BG,
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)"}},
    ]
    if recovered_count:
        reqs.append({"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 1 + recovered_count,
                      "startColumnIndex": 0, "endColumnIndex": col_count},
            "cell": {"userEnteredFormat": {
                "backgroundColor": GREEN,
                "textFormat": {"bold": True}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)"}})
    gwsg_batch(reqs)
    return recovered_count


def main():
    # --- Companies tab ---
    comps = load_rows(os.path.join(OUT, "recovered_companies_clean.csv"), "company")
    comp_rows = []
    for r, name, src, conf in comps:
        comp_rows.append([
            r["id"], r["domain"], r.get("website", ""), name, src, conf,
            result_label(src, name),
        ])
    header = ["HubSpot ID", "Domain", "Website", "Recovered Name", "Source", "Confidence", "Result"]
    rc = rewrite_tab("Scrape Pass - Companies", 0000000, header, comp_rows, len(header))
    print(f"Companies tab: {len(comp_rows)} rows, {rc} recovered", flush=True)

    # --- Contacts tab ---
    conts = load_rows(os.path.join(OUT, "recovered_contacts_clean.csv"), "contact")
    cont_rows = []
    for r, name, src, conf in conts:
        cont_rows.append([
            r["id"], r.get("email", ""), r["domain"], name, src, conf,
            result_label(src, name),
        ])
    header = ["HubSpot ID", "Email", "Domain", "Recovered Company Name", "Source", "Confidence", "Result"]
    rc = rewrite_tab("Scrape Pass - Contacts", 0000000, header, cont_rows, len(header))
    print(f"Contacts tab: {len(cont_rows)} rows, {rc} recovered", flush=True)

    # --- Domains tab ---
    doms = load_rows(os.path.join(OUT, "domain_results_clean.csv"), "domain")
    dom_rows = []
    for r, name, src, conf in doms:
        dom_rows.append([
            r["domain"], name, src, conf, fix_mojibake(r.get("meta_desc", ""))[:300],
            result_label(src, name),
        ])
    header = ["Domain", "Recovered Name", "Source", "Confidence", "Meta Description", "Result"]
    rc = rewrite_tab("Scrape Pass - Domains", 0000000, header, dom_rows, len(header))
    print(f"Domains tab: {len(dom_rows)} rows, {rc} recovered", flush=True)


if __name__ == "__main__":
    main()
