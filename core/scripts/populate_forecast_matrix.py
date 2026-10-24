#!/usr/bin/env python3
import json, subprocess, sys

DOC = "REDACTED_GOOGLE_ID"

rows = [
    ["Forecast Category", "Qualified?", "Active Motion?", "Buyer Commitment", "Confidence", "Counts Toward Forecast"],
    ["Not Forecasted", "No / unqualified", "No / stalled", "None", "-", "No"],
    ["Pipeline", "Yes", "Yes", "None", "<50%", "No"],
    ["Best Case", "Yes", "Yes", "Soft / verbal interest", "50-60%", "Partial"],
    ["Commit", "Yes", "Yes", "Firm / decision-maker", "60%+", "Yes"],
    ["Closed Won", "Yes", "Signed", "Executed contract", "100%", "Yes"],
]

def gws(args):
    r = subprocess.run(["gwsg"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        print("ERR:", r.stderr, file=sys.stderr)
        sys.exit(1)
    return json.loads(r.stdout)

doc = gws(["docs","documents","get","--params", json.dumps({"documentId": DOC})])
content = doc["body"]["content"]

table = None
for e in content:
    if "table" in e:
        table = e["table"]
        break
if not table:
    print("No table found", file=sys.stderr)
    sys.exit(1)

cell_map = []
for r in table["tableRows"]:
    row_cells = []
    for c in r["tableCells"]:
        idx = c["content"][0]["startIndex"]
        row_cells.append(idx)
    cell_map.append(row_cells)

requests = []
for ri, row in enumerate(rows):
    for ci, val in enumerate(row):
        idx = cell_map[ri][ci]
        requests.append({"insertText": {"location": {"index": idx}, "text": val}})

gws(["docs","documents","batchUpdate","--params", json.dumps({"documentId": DOC}), "--json", json.dumps({"requests": requests})])
print("Table populated:", len(rows), "rows x", len(rows[0]), "cols")
