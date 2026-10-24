#!/usr/bin/env python3
"""
Clean news articles older than 7 days from {{AE_4}}'s Prospecting Tracker.
Runs via gwsg (Google Sheets API).
"""

import subprocess
import json
import sys
import re
from datetime import datetime, timedelta

SHEET_ID = "REDACTED_GOOGLE_ID"
CUTOFF_DAYS = 7

def gwsg(args, input_data=None):
    cmd = ["gwsg"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, input=input_data)
    if result.returncode != 0:
        return None, result.stderr
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError:
        return result.stdout, None

def get_all_sheets():
    data, err = gwsg(["sheets", "spreadsheets", "get", "--params",
                      json.dumps({"spreadsheetId": SHEET_ID})])
    if err or not data:
        print(f"Error getting sheets: {err}")
        return []
    sheets = []
    for s in data.get("sheets", []):
        props = s.get("properties", {})
        sheets.append({
            "title": props.get("title"),
            "sheetId": props.get("sheetId"),
            "rowCount": props.get("gridProperties", {}).get("rowCount", 50),
            "colCount": props.get("gridProperties", {}).get("columnCount", 26),
        })
    return sheets

def get_sheet_values(sheet_title, max_row=60):
    range_name = f"{sheet_title}!A1:Z{max_row}"
    data, err = gwsg(["sheets", "spreadsheets", "values", "get", "--params",
                      json.dumps({"spreadsheetId": SHEET_ID, "range": range_name})])
    if err or not data:
        return []
    return data.get("values", [])

def parse_date(date_str):
    """Parse MM/DD or MM/DD/YY date string. Assume current year if no year."""
    if not date_str:
        return None
    # Try MM/DD
    m = re.match(r'^(\d{1,2})/(\d{1,2})$', date_str.strip())
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = datetime.now().year
        try:
            return datetime(year, month, day)
        except ValueError:
            return None
    # Try MM/DD/YY or MM/DD/YYYY
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2,4})$', date_str.strip())
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = int(m.group(3))
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day)
        except ValueError:
            return None
    return None

def find_section_bounds(values):
    """Find start and end row (0-indexed) of RECENT NEWS section.
    
    Some tabs (e.g. Leidos) lack the 'RECENT NEWS' header and instead just have
    date rows starting after the company overview block. Detect those too.
    """
    news_start = None
    news_end = None

    # Primary: explicit RECENT NEWS header
    for i, row in enumerate(values):
        if row and "RECENT NEWS" in str(row[0]).upper():
            news_start = i + 1  # row after the header
            break

    # Fallback: look for the first date-looking row if no header found
    if news_start is None:
        for i, row in enumerate(values):
            if row and parse_date(str(row[0])):
                news_start = i
                break

    if news_start is None:
        return None, None

    for i in range(news_start, len(values)):
        row = values[i]
        if row and any(
            kw in str(row[0]).upper()
            for kw in ["CURRENT STATE", "NEXT STEPS", "PARTNER", "CURRENT STATUS", "LAST ACTIVITY"]
        ):
            news_end = i
            break
    if not news_end:
        news_end = min(news_start + 12, len(values))
    return news_start, news_end

def clean_sheet(sheet_title):
    values = get_sheet_values(sheet_title)
    if not values:
        return False, "no data"

    news_start, news_end = find_section_bounds(values)
    if news_start is None:
        return False, "no RECENT NEWS section found"

    cutoff = datetime.now() - timedelta(days=CUTOFF_DAYS)
    
    # Collect the news rows in the section
    section_rows = values[news_start:news_end]
    
    kept = []
    removed = 0
    for row in section_rows:
        if not row or not row[0]:
            # Empty row — skip, we'll rebuild with empty rows
            continue
        date = parse_date(str(row[0]))
        if date is None:
            # Not a date row — keep as-is (might be a sub-header or something)
            kept.append(row)
            continue
        if date >= cutoff:
            kept.append(row)
        else:
            removed += 1
            print(f"  [{sheet_title}] Removing: {row[0]} — {row[1] if len(row) > 1 else ''}")

    if removed == 0:
        return True, "nothing to remove"

    # Rebuild section: kept articles + empty rows to fill
    section_size = news_end - news_start
    new_section = kept[:]
    while len(new_section) < section_size:
        new_section.append([])

    # Write back the section
    range_name = f"{sheet_title}!A{news_start + 1}:C{news_end}"
    # Build the payload — only columns A, B, C (date, title, url)
    write_values = []
    for row in new_section:
        if not row:
            write_values.append(["", "", ""])
        else:
            write_values.append([
                row[0] if len(row) > 0 else "",
                row[1] if len(row) > 1 else "",
                row[2] if len(row) > 2 else "",
            ])

    payload = {
        "spreadsheetId": SHEET_ID,
        "range": range_name,
        "valueInputOption": "USER_ENTERED",
        "resource": {
            "range": range_name,
            "majorDimension": "ROWS",
            "values": write_values
        }
    }

    result, err = gwsg(["sheets", "spreadsheets", "values", "update", "--params",
                        json.dumps(payload)])
    if err:
        return False, f"write error: {err}"

    return True, f"removed {removed} article(s)"

def main():
    print(f"Cutoff date: {(datetime.now() - timedelta(days=CUTOFF_DAYS)).strftime('%m/%d/%Y')}")
    print(f"Today: {datetime.now().strftime('%m/%d/%Y')}\n")

    sheets = get_all_sheets()
    skip_sheets = {"Summary"}  # Don't touch the summary tab

    total_removed = 0
    errors = []

    for sheet in sheets:
        title = sheet["title"]
        if title in skip_sheets:
            continue

        ok, msg = clean_sheet(title)
        if not ok:
            errors.append(f"{title}: {msg}")
        elif "removed" in msg:
            count = int(re.search(r'\d+', msg).group())
            total_removed += count
            print(f"  [{title}] ✓ {msg}")

    print(f"\nDone. Total articles removed: {total_removed}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors:
            print(f"  {e}")

if __name__ == "__main__":
    main()
