#!/usr/bin/env python3
import json, subprocess

rows = json.load(open("/tmp/gtm_agent_results.json"))
SPREADSHEET = "REDACTED_GOOGLE_ID"

# Read sheet to map email -> row number
out = subprocess.run(
    ["gwsg", "sheets", "+read", "--spreadsheet", SPREADSHEET,
     "--range", "Sheet1!A1:L201", "--format", "json"],
    capture_output=True, text=True, check=True).stdout
d = json.loads(out)
vals = d["values"]
hdr = vals[0]
ei = hdr.index("Email")
pi = hdr.index("Phone")
# email -> (row_index_1based, current_phone)
email_row = {}
for i, r in enumerate(vals[1:], start=2):
    em = str(r[ei]).strip() if len(r) > ei else ""
    ph = str(r[pi]).strip() if len(r) > pi else ""
    if em:
        email_row[em] = (i, ph)

# Extract phone from waterfall cell outputs
updates = []
found = 0
for r in rows:
    cells = r.get("cells") or {}
    wf = cells.get("personal_phone_number_by_linkedin_url_waterfall_01gg") or {}
    pe = cells.get("person_enrich_by_floqer_01lq") or {}
    ph = (wf.get("outputs") or {}).get("phone_number") or (pe.get("outputs") or {}).get("phone_number") or ""
    em = (r.get("inputs") or {}).get("email", "")
    if ph and em in email_row:
        row_i, cur = email_row[em]
        if not cur:  # only fill gaps, never overwrite
            updates.append({"range": f"Sheet1!K{row_i}", "values": [[ph]]})
            found += 1

print(f"Phones to write back: {found}")
if updates:
    with open("/tmp/gtm_agent_updates.json", "w") as f:
        json.dump({"valueInputOption": "USER_ENTERED", "data": updates}, f)
    subprocess.run(
        ["gwsg", "sheets", "spreadsheets", "values", "batchUpdate",
         "--params", json.dumps({"spreadsheetId": SPREADSHEET}),
         "--json", json.dumps({"valueInputOption": "USER_ENTERED", "data": updates})],
        check=True)
    print("Wrote back to sheet.")
