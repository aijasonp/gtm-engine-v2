#!/usr/bin/env python3
"""Add Project Management tab to FY26 New Biz Sales Stage Revision sheet."""
import json, subprocess, sys

SHEET_ID = "REDACTED_GOOGLE_ID"

def gwsg(*args):
    r = subprocess.run(["gwsg"] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        print("ERR:", r.stderr, file=sys.stderr)
        sys.exit(1)
    return json.loads(r.stdout)

def add_sheet(title):
    gwsg("sheets", "spreadsheets", "batchUpdate",
         "--params", json.dumps({"spreadsheetId": SHEET_ID}),
         "--json", json.dumps({"requests": [{"addSheet": {"properties": {"title": title}}}]}))

def write_range(tab, rng, values):
    body = {"range": f"'{tab}'!{rng}", "majorDimension": "ROWS", "values": values}
    gwsg("sheets", "spreadsheets", "values", "batchUpdate",
         "--params", json.dumps({"spreadsheetId": SHEET_ID}),
         "--json", json.dumps({"valueInputOption": "USER_ENTERED", "data": [body]}))

# Project management / RACI
pm = [
    ["Role", "Name", "Responsibility"],
    ["Executive Sponsor", "{{SALES_LEADER}}", "Executive sponsor for the FY26 New Biz Sales Stage Revision project"],
    ["Executive Sponsor", "{{AE_1}}", "Executive sponsor for the FY26 New Biz Sales Stage Revision project"],
    ["Supporting Stakeholder", "SE Leader", "Supporting stakeholder (Solutions Engineering)"],
    ["Supporting Stakeholder", "Sales Development Leader", "Supporting stakeholder (Sales Development)"],
    ["HubSpot Contractor", "Dinesh", "HubSpot implementation / configuration contractor"],
    ["Project Manager", "{{REVOPS_1}}", "Project manager, owns delivery and coordination"],
    ["QA", "{{REVOPS_1}}", "QA testing"],
    ["QA", "Dinesh (HubSpot Contractor)", "QA testing"],
    ["QA", "AE Tester", "QA testing (Account Executive tester)"],
    ["QA", "XDR Tester", "QA testing (XDR tester)"],
]

add_sheet("Project Management")
write_range("Project Management", "A1", pm)

print("DONE")
