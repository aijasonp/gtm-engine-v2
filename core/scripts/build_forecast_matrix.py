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

# Get current end index
doc = gws(["docs","documents","get","--params", json.dumps({"documentId": DOC})])
end = doc["body"]["content"][-1]["endIndex"]
print("end index:", end)

# Insert table at end-1
req = {"requests": [{"insertTable": {"rows": len(rows), "columns": len(rows[0]), "location": {"index": end - 1}}}]}
gws(["docs","documents","batchUpdate","--params", json.dumps({"documentId": DOC}), "--json", json.dumps(req)])

# Re-read to find table cell indices
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

# Build cell index map
cell_map = []
for r in table["tableRows"]:
    row_cells = []
    for c in r["tableCells"]:
        idx = c["content"][0]["startIndex"]
        row_cells.append(idx)
    cell_map.append(row_cells)

# Insert text in REVERSE order (bottom-right to top-left) so indices don't shift
requests = []
for ri in range(len(rows)-1, -1, -1):
    for ci in range(len(rows[0])-1, -1, -1):
        idx = cell_map[ri][ci]
        requests.append({"insertText": {"location": {"index": idx}, "text": rows[ri][ci]}})

gws(["docs","documents","batchUpdate","--params", json.dumps({"documentId": DOC}), "--json", json.dumps({"requests": requests})])
print("Table populated:", len(rows), "rows x", len(rows[0]), "cols")
