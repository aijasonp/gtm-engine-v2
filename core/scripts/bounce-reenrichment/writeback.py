#!/usr/bin/env python3
"""Write enrichment results back to the Google Sheet."""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET_ID = "REDACTED_GOOGLE_ID"
TAB = "Bounced - Needs Enrichment"

rows = json.load(open(os.path.join(HERE, "final_rows.json")))

def gws_update(rng, values_json):
    params = {"spreadsheetId": SHEET_ID, "range": rng, "valueInputOption": "RAW"}
    body = {"range": rng, "majorDimension": "ROWS", "values": values_json}
    cmd = [
        os.path.expanduser("~/.npm-global/bin/gws"),
        "sheets", "spreadsheets", "values", "update",
        "--params", json.dumps(params),
        "--json", json.dumps(body),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        print("FAIL", rng, (out.stderr or out.stdout)[:400])
        return False
    try:
        d = json.loads(out.stdout)
        print(f"OK {rng}: cells={d.get('updatedCells')}")
    except Exception:
        print("OK?", rng, out.stdout[:200])
    return True

src_map = {
    "moltsets:A": "MoltSets (risk A — validated)",
    "moltsets:B": "MoltSets (risk B)",
    "moltsets:C": "MoltSets (risk C — catch-all, verify before send)",
    "clay_email:leadmagic": "Clay email waterfall — LeadMagic",
    "clay_email:findymail": "Clay email waterfall — Findymail",
    "clay_email:datagma": "Clay email waterfall — Datagma",
    "clay_miss": "MoltSets + Clay miss (no email found)",
    "clay_miss_same_or_none": "MoltSets + Clay miss (no email found)",
}

for r in rows:
    rn = r["row"]
    new_email = r.get("final_email", "")
    new_email_src = r.get("final_email_source", "")
    src_label = src_map.get(new_email_src, new_email_src or "MoltSets + Clay miss")
    phone = r.get("clay_phone", "")
    if new_email and phone:
        status = "✅ New email + direct dial found"
    elif new_email:
        status = "✅ New email found"
    elif phone:
        status = "☎️ Direct dial found only (no new email)"
    else:
        status = "❌ No email, no dial"
    if rn == 11 and not new_email:
        status = "❌ No new email — Clay waterfall returned the same bounced address only"
    gws_update(f"'{TAB}'!M{rn}:P{rn}", [[new_email, src_label, phone, status]])

# Phone col J updates where empty + we have a phone
for r in rows:
    if r.get("clay_phone") and not r.get("phone_existing"):
        gws_update(f"'{TAB}'!J{r['row']}", [[r["clay_phone"]]])

# David Yoken LinkedIn fix — sheet col D was empty but notes confirmed dave-yoken
gws_update(f"'{TAB}'!D2", [["https://www.linkedin.com/in/dave-yoken"]])

print("writeback complete")
