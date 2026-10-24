#!/usr/bin/env python3
"""Write values + formatting to the board forecast sheet."""
import os
import json, subprocess, sys

OUT = os.path.expanduser("~/.openclaw/workspace/output")
SHEET_ID = "REDACTED_GOOGLE_ID"
tabs = json.load(open(f"{OUT}/board-forecast-tabs.json"))

SHEET_IDS = {"Q3 Closed Won": 0, "Q3 Open (Closable)": 0000000, "Q4 Pipeline": 0000000, "Summary": 0000000}

def gwsg(args):
    r = subprocess.run(["gwsg"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        print("GWSG ERROR:", r.stderr, file=sys.stderr)
        raise RuntimeError(r.stderr)
    return r.stdout

# ---------- Write values per tab ----------
data = []
for tab, rows in tabs.items():
    # Convert to A1 values; amounts as numbers, dates as strings
    values = []
    for row in rows:
        vals = []
        for cell in row:
            if isinstance(cell, (int, float)) and not isinstance(cell, bool):
                vals.append(cell)
            else:
                vals.append(str(cell))
        values.append(vals)
    data.append({"range": f"'{tab}'!A1", "values": values})

body = {"valueInputOption": "USER_ENTERED", "data": data}
gwsg(["sheets", "spreadsheets", "values", "batchUpdate",
      "--params", json.dumps({"spreadsheetId": SHEET_ID}),
      "--json", json.dumps(body)])
print("Values written to all tabs.")

# ---------- Formatting ----------
requests = []
ORANGE = {"red": 0.9098, "green": 0.3412, "blue": 0.0510}  # #E8570D
WHITE = {"red": 1, "green": 1, "blue": 1}

for tab, rows in tabs.items():
    sid = SHEET_IDS[tab]
    ncols = max(len(r) for r in rows)
    nrows = len(rows)
    # Header row (row 1) orange bg + white bold
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 0, "endColumnIndex": ncols},
            "cell": {"userEnteredFormat": {
                "backgroundColor": ORANGE,
                "textFormat": {"foregroundColor": WHITE, "bold": True}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)"
        }
    })
    # Freeze header row
    requests.append({
        "updateSheetProperties": {
            "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"
        }
    })
    # Auto-resize columns
    requests.append({
        "autoResizeDimensions": {
            "dimensions": {"sheetId": sid, "dimension": "COLUMNS",
                           "startIndex": 0, "endIndex": ncols}
        }
    })
    # Currency formatting on amount columns
    # Find amount column index (2nd column = index 1 for data tabs; Summary col B)
    if tab in ("Q3 Closed Won", "Q3 Open (Closable)", "Q4 Pipeline"):
        amt_col = 2  # column C (index 2)
        requests.append({
            "repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": nrows,
                          "startColumnIndex": amt_col-1, "endColumnIndex": amt_col},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": "CURRENCY", "pattern": "$#,##0"}}},
                "fields": "userEnteredFormat.numberFormat"
            }
        })
    # Bold TOTAL row (last row)
    requests.append({
        "repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": nrows-1, "endRowIndex": nrows,
                      "startColumnIndex": 0, "endColumnIndex": ncols},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat"
        }
    })

# Summary tab: currency on column B (index 1) for numeric rows
sid = SHEET_IDS["Summary"]
nrows = len(tabs["Summary"])
requests.append({
    "repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": nrows,
                  "startColumnIndex": 1, "endColumnIndex": 2},
        "cell": {"userEnteredFormat": {"numberFormat": {"type": "CURRENCY", "pattern": "$#,##0"}}},
        "fields": "userEnteredFormat.numberFormat"
    }
})

body = {"requests": requests}
gwsg(["sheets", "spreadsheets", "batchUpdate",
      "--params", json.dumps({"spreadsheetId": SHEET_ID}),
      "--json", json.dumps(body)])
print("Formatting applied.")
