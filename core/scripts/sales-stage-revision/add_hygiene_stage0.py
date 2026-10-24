#!/usr/bin/env python3
"""Add 'Not a real deal / pipeline hygiene' to Stage-0 Closed Lost picklist (C2)."""
import json, subprocess, sys

SHEET_ID = "REDACTED_GOOGLE_ID"

def gwsg(*args):
    r = subprocess.run(["gwsg"] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        print("ERR:", r.stderr, file=sys.stderr)
        sys.exit(1)
    return json.loads(r.stdout)

new_val = "Not Qualified - Timing, Not Qualified - Need, Not Qualified - Budget, Not Qualified - No authority, No show - Unresponsive, Not a real deal / pipeline hygiene"
body = {"range": "'Closed Lost Rules'!C2", "majorDimension": "ROWS", "values": [[new_val]]}
gwsg("sheets", "spreadsheets", "values", "batchUpdate",
     "--params", json.dumps({"spreadsheetId": SHEET_ID}),
     "--json", json.dumps({"valueInputOption": "USER_ENTERED", "data": [body]}))

print("DONE")
