#!/usr/bin/env python3
"""Fix Outreach Ready tab: move phone numbers from LinkedIn URL col (H) to Phone col (I),
and move LinkedIn URLs from Talk Track col (V) to LinkedIn URL col (H), then clear V."""

import os
import json
import subprocess
import sys

SHEET_ID = "REDACTED_GOOGLE_ID"
GWSG = os.path.expanduser("~/.local/bin/gwsg")

def gwsg_read(range_):
    result = subprocess.run(
        [GWSG, "sheets", "+read", "--spreadsheet", SHEET_ID, "--range", range_],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR reading {range_}: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)

def gwsg_batch_update(data):
    body = {
        "valueInputOption": "RAW",
        "data": data
    }
    result = subprocess.run(
        [GWSG, "sheets", "spreadsheets", "values", "batchUpdate",
         "--params", json.dumps({"spreadsheetId": SHEET_ID}),
         "--json", json.dumps(body)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR batch update: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)

# Column indices (0-based)
COL_H = 7   # LinkedIn URL
COL_I = 8   # Phone
COL_V = 21  # Talk Track (where LinkedIn URLs got misplaced)

# Read all Outreach Ready data
print("Reading Outreach Ready tab...")
data = gwsg_read("'Outreach Ready'!A1:Z100")
rows = data.get("values", [])
header = rows[0] if rows else []
print(f"Header row: {[f'{chr(65+i)}={v}' for i,v in enumerate(header)]}")

updates = []
fixes_summary = []

for row_idx, row in enumerate(rows[1:], start=2):  # start=2 because row 1 is header
    # Pad row to at least 26 columns
    while len(row) <= max(COL_H, COL_I, COL_V):
        row.append("")
    
    h_val = row[COL_H] if len(row) > COL_H else ""  # Current LinkedIn URL col value
    i_val = row[COL_I] if len(row) > COL_I else ""  # Current Phone col value  
    v_val = row[COL_V] if len(row) > COL_V else ""  # Current Talk Track col value
    
    name = row[1] if len(row) > 1 else f"Row {row_idx}"
    
    new_h = h_val
    new_i = i_val
    new_v = v_val
    changed = False
    
    # Check if V has a LinkedIn URL
    v_has_linkedin = v_val.startswith("https://linkedin.com") or v_val.startswith("http://linkedin.com")
    # Check if H has a phone number (not a LinkedIn URL, starts with +)
    h_has_phone = h_val.startswith("+") or (h_val.isdigit() and len(h_val) > 7)
    h_has_linkedin = h_val.startswith("https://linkedin.com") or h_val.startswith("http://linkedin.com")
    
    if h_has_phone and v_has_linkedin:
        # Phone in H, LinkedIn in V → move phone to I, LinkedIn to H, clear V
        new_h = v_val
        new_i = h_val
        new_v = ""
        changed = True
        fixes_summary.append(f"Row {row_idx} ({name}): phone '{h_val}' → col I, LinkedIn '{v_val}' → col H, cleared V")
    elif v_has_linkedin and not h_has_linkedin:
        # LinkedIn in V, H is empty → move LinkedIn to H, clear V
        new_h = v_val
        new_v = ""
        changed = True
        fixes_summary.append(f"Row {row_idx} ({name}): LinkedIn '{v_val}' → col H, cleared V")
    elif h_has_phone and not v_has_linkedin:
        # Phone in H, no LinkedIn in V → move phone to I, clear H
        new_i = h_val
        new_h = ""
        changed = True
        fixes_summary.append(f"Row {row_idx} ({name}): phone '{h_val}' → col I, cleared H")
    
    if changed:
        # Update H (LinkedIn URL col) = col 8 in 1-indexed = H
        updates.append({
            "range": f"'Outreach Ready'!H{row_idx}",
            "majorDimension": "ROWS",
            "values": [[new_h]]
        })
        # Update I (Phone col)
        updates.append({
            "range": f"'Outreach Ready'!I{row_idx}",
            "majorDimension": "ROWS",
            "values": [[new_i]]
        })
        # Update V (Talk Track col - clear the misplaced LinkedIn URL)
        updates.append({
            "range": f"'Outreach Ready'!V{row_idx}",
            "majorDimension": "ROWS",
            "values": [[new_v]]
        })

print(f"\n=== CHANGES TO APPLY ({len(fixes_summary)} rows) ===")
for fix in fixes_summary:
    print(f"  {fix}")

if not updates:
    print("\nNo changes needed.")
    sys.exit(0)

print(f"\nApplying {len(updates)} cell updates...")
result = gwsg_batch_update(updates)
print("\n=== DONE ===")
print(f"Updated {result.get('totalUpdatedCells', '?')} cells across {result.get('totalUpdatedRows', '?')} rows")
