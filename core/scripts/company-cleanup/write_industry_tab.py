#!/usr/bin/env python3
"""Write the Industry Pass results to a new tab on the audit sheet."""
import csv, json, os, subprocess, sys, urllib.request

WS = os.path.expanduser("~/.openclaw/workspace")
OUT = os.path.join(WS, "output", "company-cleanup")
SHEET = "REDACTED_GOOGLE_ID"
GWSG = os.path.expanduser("~/.local/bin/gwsg")
TAB = "Industry Pass - Companies"

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
        body = e.read().decode()[:500]
        raise RuntimeError(f"HTTP {e.code}: {body}") from e


def batch(requests_list):
    return api("POST", ":batchUpdate", {"requests": requests_list})


def update_values(range_a1, values):
    from urllib.parse import quote
    body = {"range": range_a1, "majorDimension": "ROWS", "values": values}
    return api("PUT", f"/values/{quote(range_a1, safe='')}?valueInputOption=RAW", body)


def main():
    rows = list(csv.DictReader(open(os.path.join(OUT, "industry_pass_companies.csv"))))
    n = len(rows)
    recovered = sum(1 for r in rows if r["status"] == "recovered")

    # 1. create tab (ignore error if exists -> then grab id)
    sheet_id = None
    try:
        j = batch([{"addSheet": {"properties": {"title": TAB, "gridProperties": {"rowCount": n + 60, "columnCount": 8}}}}])
        sheet_id = j["replies"][0]["addSheet"]["properties"]["sheetId"]
        print(f"created tab, sheetId={sheet_id}", flush=True)
    except Exception as e:
        if "already exists" in str(e):
            j = api("GET", "?fields=sheets.properties")
            for s in j["sheets"]:
                if s["properties"]["title"] == TAB:
                    sheet_id = s["properties"]["sheetId"]
            batch([{"updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"rowCount": n + 60}},
                "fields": "gridProperties.rowCount"}}])
            print(f"tab exists, sheetId={sheet_id}, resized", flush=True)
        else:
            raise

    # 2. write values
    header = ["HubSpot ID", "Domain", "Name", "Industry", "Confidence", "Evidence", "Result"]
    values = [header]
    for r in rows:
        result = {"recovered": "RECOVERED", "jev-error": "CLASSIFY ERROR", "no-data": "NO DATA (dead domain / no site text)"}.get(r["status"], r["status"])
        values.append([r["id"], r["domain"], r["name"], r["industry_label"],
                       r["jev_confidence"], r["evidence"], result])
    update_values(f"'{TAB}'!A1", values)
    print(f"wrote {len(values)} rows", flush=True)

    # 3. formatting
    reqs = [
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": 7},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_BG,
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)"}},
    ]
    if recovered:
        reqs.append({"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 1 + recovered,
                      "startColumnIndex": 0, "endColumnIndex": 7},
            "cell": {"userEnteredFormat": {"backgroundColor": GREEN, "textFormat": {"bold": True}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)"}})
    batch(reqs)
    print(f"formatted: {recovered} recovered rows highlighted", flush=True)
    print(json.dumps({"sheetId": sheet_id, "rows": n, "recovered": recovered}))


if __name__ == "__main__":
    main()
