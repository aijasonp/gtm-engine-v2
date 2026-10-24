#!/usr/bin/env python3
"""Build the board forecast sheet content and write via gwsg."""
import os
import json, subprocess, sys
from datetime import date

OUT = os.path.expanduser("~/.openclaw/workspace/output")
SHEET_ID = "REDACTED_GOOGLE_ID"
d = json.load(open(f"{OUT}/board-forecast-analysis.json"))

q3_won = d["q3_won"]
q3_open = d["q3_open"]
q4_pipe = d["q4_pipe"]

from datetime import date as _date
def _d(v):
    if isinstance(v, str):
        try:
            return _date.fromisoformat(v[:10])
        except Exception:
            return None
    return v
for _r in q3_won + q3_open + q4_pipe:
    _r["closedate"] = _d(_r.get("closedate"))

def gwsg(args):
    r = subprocess.run(["gwsg"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        print("GWSG ERROR:", r.stderr, file=sys.stderr)
        raise RuntimeError(r.stderr)
    return r.stdout

# ---------- Build tab data ----------
def build_q3_won():
    rows = [["Deal Name", "Company", "Amount", "Close Date", "Owner", "Deal Type", "Pipeline"]]
    for r in sorted(q3_won, key=lambda x: x["closedate"]):
        rows.append([r["name"], r["company"], r["amount"], str(r["closedate"]), r["owner"], r["dealtype"], "Sales Pipeline"])
    total = sum(r["amount"] for r in q3_won)
    rows.append(["TOTAL", "", total, "", "", "", ""])
    return rows

def build_q3_open():
    rows = [["Deal Name", "Company", "Amount", "Stage", "Forecast Category", "Close Date", "Owner", "Next Step", "Slipped"]]
    for r in sorted(q3_open, key=lambda x: -x["amount"]):
        slipped = ""
        if r["closedate"] and r["closedate"] < date(2026, 9, 23):
            slipped = f"SLIPPED - was {r['closedate']}"
        rows.append([r["name"], r["company"], r["amount"], r["stage_label"], r["fc"] or "", str(r["closedate"]), r["owner"], r["next_step"], slipped])
    total = sum(r["amount"] for r in q3_open)
    rows.append(["TOTAL", "", total, "", "", "", "", "", ""])
    return rows

def build_q4_pipe():
    rows = [["Deal Name", "Company", "Amount", "Stage", "Forecast Category", "Probability %", "Close Date", "Owner", "Deal Type", "Next Step", "Last Modified"]]
    for r in sorted(q4_pipe, key=lambda x: (x["closedate"] or date(2099,1,1), -x["amount"])):
        prob = int(round(r["stage_prob"] * 100))
        rows.append([r["name"], r["company"], r["amount"], r["stage_label"], r["fc"] or "", prob, str(r["closedate"]), r["owner"], r["dealtype"], r["next_step"], r["lastmod"]])
    total = sum(r["amount"] for r in q4_pipe)
    rows.append(["TOTAL", "", total, "", "", "", "", "", "", "", ""])
    return rows

def build_summary():
    q3_won_total = sum(r["amount"] for r in q3_won)
    q3_open_total = sum(r["amount"] for r in q3_open)
    slipped = [r for r in q3_open if r["closedate"] and r["closedate"] < date(2026, 9, 23)]
    in_q = [r for r in q3_open if r["closedate"] and r["closedate"] >= date(2026, 9, 23)]
    slipped_total = sum(r["amount"] for r in slipped)
    in_q_total = sum(r["amount"] for r in in_q)
    q4_total = sum(r["amount"] for r in q4_pipe)
    q4_weighted = sum(r["amount"] * r["stage_prob"] for r in q4_pipe)

    # Q4 subtotal by stage
    by_stage = {}
    for r in q4_pipe:
        by_stage.setdefault(r["stage_label"], []).append(r)

    rows = []
    rows.append(["{{COMPANY}} Board Forecast", "", ""])
    rows.append(["As of", "2026-09-23", ""])
    rows.append(["Filter", "New Business + Upsell only (renewals, services, and untyped deals excluded)", ""])
    rows.append([])
    rows.append(["Q3 2026 CLOSED WON", "", ""])
    rows.append(["Total", q3_won_total, f"{len(q3_won)} deals"])
    rows.append([])
    rows.append(["Q3 2026 OPEN (closable by Sep 30)", "", ""])
    rows.append(["Total", q3_open_total, f"{len(q3_open)} deals"])
    rows.append(["  Slipped (past close date, still open)", slipped_total, f"{len(slipped)} deals"])
    rows.append(["  In-quarter (close date Sep 23-30)", in_q_total, f"{len(in_q)} deals"])
    rows.append([])
    rows.append(["Q4 2026 PIPELINE", "", ""])
    rows.append(["Total", q4_total, f"{len(q4_pipe)} deals"])
    rows.append(["Weighted (amount x stage probability)", q4_weighted, ""])
    rows.append([])
    rows.append(["Q4 Pipeline by Stage", "", ""])
    for stage in sorted(by_stage.keys()):
        st = sum(r["amount"] for r in by_stage[stage])
        rows.append([f"  {stage}", st, f"{len(by_stage[stage])} deals"])
    return rows

tabs = {
    "Q3 Closed Won": build_q3_won(),
    "Q3 Open (Closable)": build_q3_open(),
    "Q4 Pipeline": build_q4_pipe(),
    "Summary": build_summary(),
}

# Save tab content for reference
json.dump(tabs, open(f"{OUT}/board-forecast-tabs.json", "w"), indent=2, default=str)

# ---------- Write to sheet ----------
# Rename default sheet to first tab, add others
# Get current sheets
out = gwsg(["sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": SHEET_ID})])
import re
sheet_ids = re.findall(r'"sheetId":\s*(\d+)', out)
print("existing sheetIds:", sheet_ids)

# Build batchUpdate for sheet setup: rename first, add 3 more
requests = []
# rename first sheet
requests.append({"updateSheetProperties": {"properties": {"sheetId": int(sheet_ids[0]), "title": "Q3 Closed Won"}, "fields": "title"}})
# add sheets
for title in ["Q3 Open (Closable)", "Q4 Pipeline", "Summary"]:
    requests.append({"addSheet": {"properties": {"title": title}}})

body = {"requests": requests}
gwsg(["sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": SHEET_ID}), "--json", json.dumps(body)])
print("Sheets added/renamed.")

# Get sheet ids for each tab
out = gwsg(["sheets", "spreadsheets", "get", "--params", json.dumps({"spreadsheetId": SHEET_ID})])
# parse titles -> sheetId
import re
titles = re.findall(r'"title":\s*"([^"]+)"', out)
ids = re.findall(r'"sheetId":\s*(\d+)', out)
print("titles:", titles)
print("ids:", ids)
