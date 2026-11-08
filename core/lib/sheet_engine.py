#!/usr/bin/env python3
"""sheet_engine.py: color-coded Google Sheet builder that rebuilds in place.

Vendored from shawnla90/gtm-coding-agent (MIT; see THIRD_PARTY.md) and changed for this engine:
  * large, readable fonts by default (body 12, header 13, dashboard title 20). Override with FONTS.
  * credentials from GOOGLE_SERVICE_ACCOUNT_FILE, or GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET /
    GOOGLE_REFRESH_TOKEN (already in .env.example), or a gspread OAuth token file. Headless friendly.
  * request building is split from I/O, so every formatting rule is unit-testable without Google.

Features: red-yellow-green score gradient, categorical color maps, banding, frozen header, filters,
sized columns, a styled dashboard tab, anyone-with-link sharing, and in-place rebuild by sheet id
so a link already sent to a design partner keeps working.

    url, tabs = build({
        "title": "Q4 reachability", "key": None, "share": None,
        "dashboard": {"title": "Dashboard", "subtitle": {"title": "...", "sub": "..."},
                      "entries": [{"kind": "section", "label": "Routes"}, {"kind": "kpi", "label": "send", "value": 41}]},
        "tabs": [{"title": "Send", "df": df, "cols": [...], "widths": {"email": 260},
                  "cf": [{"type": "grad", "col": "score", "stops": (1, 3, 5)},
                         {"type": "map", "col": "grade", "map": {"A": GREEN, "D": RED}}],
                  "numeric": ["score"]}],
        "raw_tabs": [{"title": "Model", "values": [["k", "v"], ["a", 1]]}],
    })
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_TOKEN = Path.home() / ".config" / "gspread" / "token.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

FONTS = {"body": 12, "header": 13, "title": 20, "subtitle": 13, "section": 14, "kpi": 15, "bullet": 12}
ROW_PX = 30            # body row height so 12pt text is not cramped
CHAR_PX = 11           # auto column width per character at 12pt

# palette (hex without #)
NAVY = "1F3A56"
GREEN = "57BB8A"
GREEN_DK = "16653A"
GREEN_LT = "B7E1CD"
BLUE = "C9DAF8"
YELLOW = "FCE8B2"
AMBER = "FFF2CC"
GREY = "EFEFEF"
GREY_LT = "F3F3F3"
ORANGE = "FCE5CD"
RED = "E67C73"


def rgb(h: str) -> dict:
    h = h.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


def num(v):
    try:
        f = float(v)
        return int(f) if f == int(f) else f
    except (ValueError, TypeError):
        return None


def _rng(sid, r0, r1, c0, c1):
    return {"sheetId": sid, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


# ----------------------------------------------------------------------------- request builders (pure)
def r_body_font(sid, nrows, ncols, size=None):
    return [{"repeatCell": {"range": _rng(sid, 0, nrows, 0, ncols),
                            "cell": {"userEnteredFormat": {"textFormat": {"fontSize": size or FONTS["body"]},
                                                           "verticalAlignment": "MIDDLE"}},
                            "fields": "userEnteredFormat(textFormat.fontSize,verticalAlignment)"}},
            {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0,
                                                     "endIndex": nrows},
                                           "properties": {"pixelSize": ROW_PX}, "fields": "pixelSize"}}]


def r_header(sid, ncols):
    return [{"repeatCell": {"range": _rng(sid, 0, 1, 0, ncols),
                            "cell": {"userEnteredFormat": {"backgroundColor": rgb(NAVY),
                                                           "textFormat": {"foregroundColor": rgb("FFFFFF"), "bold": True,
                                                                          "fontSize": FONTS["header"]},
                                                           "verticalAlignment": "MIDDLE"}},
                            "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)"}},
            {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                                       "fields": "gridProperties.frozenRowCount"}}]


def r_band(sid, nrows, ncols):
    return {"addBanding": {"bandedRange": {"range": _rng(sid, 0, nrows, 0, ncols),
                                           "rowProperties": {"headerColor": rgb(NAVY), "firstBandColor": rgb("FFFFFF"),
                                                             "secondBandColor": rgb("EEF3F8")}}}}


def r_filter(sid, nrows, ncols):
    return {"setBasicFilter": {"filter": {"range": _rng(sid, 0, nrows, 0, ncols)}}}


def r_width(sid, col, px):
    return {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": col,
                                                    "endIndex": col + 1},
                                          "properties": {"pixelSize": px}, "fields": "pixelSize"}}


def cf_text(sid, col, nrows, value, color):
    return {"addConditionalFormatRule": {"rule": {"ranges": [_rng(sid, 1, nrows, col, col + 1)],
            "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": value}]},
                            "format": {"backgroundColor": rgb(color)}}}, "index": 0}}


def cf_grad(sid, col, nrows, stops=(1, 3, 5)):
    lo, mid, hi = stops
    return {"addConditionalFormatRule": {"rule": {"ranges": [_rng(sid, 1, nrows, col, col + 1)],
            "gradientRule": {"minpoint": {"color": rgb(RED), "type": "NUMBER", "value": str(lo)},
                             "midpoint": {"color": rgb("FFD666"), "type": "NUMBER", "value": str(mid)},
                             "maxpoint": {"color": rgb(GREEN), "type": "NUMBER", "value": str(hi)}}}, "index": 0}}


def table_values(records: list[dict], cols: list[str], numeric: set) -> list[list]:
    """Header + rows. Numeric columns become numbers; text starting with '=' is escaped so a value
    pulled from a scrape can never execute as a formula."""
    out = [list(cols)]
    for r in records:
        row = []
        for c in cols:
            v = r.get(c, "")
            v = "" if v is None or (isinstance(v, float) and v != v) else v
            if c in numeric:
                n = num(v)
                row.append(n if n is not None else "")
            else:
                s = str(v)
                row.append("'" + s if s[:1] in ("=", "+", "-", "@") and num(s) is None else s)
        out.append(row)
    return out


def auto_widths(values: list[list], min_px=90, max_px=420) -> list[int]:
    ncols = len(values[0]) if values else 0
    widths = []
    for j in range(ncols):
        longest = max((len(str(r[j])) for r in values[:200] if j < len(r)), default=8)
        widths.append(max(min_px, min(max_px, longest * CHAR_PX + 24)))
    return widths


def plan_data_tab(sid, values, widths=None, cf=None) -> list[dict]:
    cols, nrows = values[0], len(values)
    ncols = len(cols)
    reqs = r_body_font(sid, nrows, ncols) + r_header(sid, ncols)
    reqs += [r_band(sid, nrows, ncols), r_filter(sid, nrows, ncols)]
    auto = auto_widths(values)
    for j, c in enumerate(cols):
        reqs.append(r_width(sid, j, (widths or {}).get(c, auto[j])))
    for spec in cf or []:
        if spec["col"] not in cols:
            continue
        j = cols.index(spec["col"])
        if spec["type"] == "grad":
            reqs.append(cf_grad(sid, j, nrows, spec.get("stops", (1, 3, 5))))
        else:
            reqs += [cf_text(sid, j, nrows, val, color) for val, color in spec["map"].items()]
    return reqs


def plan_dashboard(sid, subtitle: dict, entries: list[dict]) -> tuple[list[list], list[dict]]:
    """(values, requests) for the dashboard tab."""
    rows, kinds = [], []
    for e in entries:
        rows.append([e.get("label", ""), e.get("value", "")])
        kinds.append(e.get("kind", "kpi"))
    values = [[subtitle.get("title", ""), ""], [subtitle.get("sub", ""), ""]] + rows
    reqs = r_body_font(sid, len(values), 4)
    reqs += [r_width(sid, 0, 470), r_width(sid, 1, 380),
             {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True}},
                                        "fields": "gridProperties.hideGridlines"}}]
    for r, fmt in ((0, {"backgroundColor": rgb(NAVY), "textFormat": {"foregroundColor": rgb("FFFFFF"), "bold": True,
                                                                    "fontSize": FONTS["title"]}}),
                   (1, {"textFormat": {"foregroundColor": rgb("5B6B7B"), "italic": True,
                                       "fontSize": FONTS["subtitle"]}})):
        reqs.append({"mergeCells": {"range": _rng(sid, r, r + 1, 0, 4), "mergeType": "MERGE_ALL"}})
        reqs.append({"repeatCell": {"range": _rng(sid, r, r + 1, 0, 4), "cell": {"userEnteredFormat": fmt},
                                    "fields": "userEnteredFormat(" + ",".join(fmt) + ")"}})
    reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0,
                                                         "endIndex": 1},
                                               "properties": {"pixelSize": 46}, "fields": "pixelSize"}})
    for i, k in enumerate(kinds):
        r = i + 2
        if k == "section":
            reqs.append({"repeatCell": {"range": _rng(sid, r, r + 1, 0, 4),
                                        "cell": {"userEnteredFormat": {"backgroundColor": rgb("DCE6F1"),
                                                                       "textFormat": {"bold": True,
                                                                                      "fontSize": FONTS["section"],
                                                                                      "foregroundColor": rgb(NAVY)}}},
                                        "fields": "userEnteredFormat(backgroundColor,textFormat)"}})
        elif k == "kpi" and str(rows[i][1]) != "":
            reqs.append({"repeatCell": {"range": _rng(sid, r, r + 1, 1, 2),
                                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True,
                                                                                      "fontSize": FONTS["kpi"],
                                                                                      "foregroundColor": rgb(GREEN_DK)},
                                                                       "horizontalAlignment": "LEFT"}},
                                        "fields": "userEnteredFormat(textFormat,horizontalAlignment)"}})
        elif k == "bullet":
            reqs.append({"mergeCells": {"range": _rng(sid, r, r + 1, 0, 4), "mergeType": "MERGE_ALL"}})
            reqs.append({"repeatCell": {"range": _rng(sid, r, r + 1, 0, 4),
                                        "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP",
                                                                       "textFormat": {"fontSize": FONTS["bullet"]}}},
                                        "fields": "userEnteredFormat(wrapStrategy,textFormat)"}})
    return values, reqs


def plan_raw_tab(sid, values, widths=None, header=True, row_colors=None, bold_rows=None) -> list[dict]:
    ncols = max(len(r) for r in values)
    reqs = r_body_font(sid, len(values), ncols)
    if header:
        reqs += r_header(sid, len(values[0]))
    for col, px in (widths or {}).items():
        if col < ncols:
            reqs.append(r_width(sid, col, px))
    for i, hexcol in (row_colors or {}).items():
        reqs.append({"repeatCell": {"range": _rng(sid, i, i + 1, 0, ncols),
                                    "cell": {"userEnteredFormat": {"backgroundColor": rgb(hexcol)}},
                                    "fields": "userEnteredFormat.backgroundColor"}})
    for i in bold_rows or []:
        reqs.append({"repeatCell": {"range": _rng(sid, i, i + 1, 0, ncols),
                                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True,
                                                                                  "fontSize": FONTS["body"],
                                                                                  "foregroundColor": rgb(NAVY)}}},
                                    "fields": "userEnteredFormat(textFormat)"}})
    return reqs


# ----------------------------------------------------------------------------- I/O
def creds(token: Path | str | None = None):
    """Service account, then refresh-token env vars, then a gspread OAuth token file."""
    sa = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if sa:
        from google.oauth2.service_account import Credentials as SACreds
        return SACreds.from_service_account_file(os.path.expanduser(sa), scopes=SCOPES)
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    cid, secret, refresh = (os.environ.get(k) for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
                                                        "GOOGLE_REFRESH_TOKEN"))
    if cid and secret and refresh:
        c = Credentials(None, refresh_token=refresh, client_id=cid, client_secret=secret,
                        token_uri="https://oauth2.googleapis.com/token", scopes=SCOPES)
        c.refresh(Request())
        return c
    token = Path(token or DEFAULT_TOKEN).expanduser()
    c = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not c.valid:
        c.refresh(Request())
        token.write_text(c.to_json())
    return c


def _records(df_or_rows) -> list[dict]:
    if hasattr(df_or_rows, "to_dict"):
        return df_or_rows.to_dict(orient="records")
    return list(df_or_rows or [])


def build(config: dict):
    """Build or rebuild a sheet. Returns (url, [tab_titles]). `df` may be a pandas DataFrame or a list of dicts."""
    import gspread
    gc = gspread.authorize(creds(config.get("token")))
    key = config.get("key")
    sh = gc.open_by_key(key) if key else gc.create(config["title"])
    # clear old tabs first so titles never collide; the API forbids deleting the last sheet,
    # so a placeholder holds the spot until the new tabs exist
    existing = sh.worksheets()
    placeholder = sh.add_worksheet(title="_rebuilding_", rows=1, cols=1)
    for ws in existing:
        sh.del_worksheet(ws)

    reqs: list = []
    if config.get("dashboard"):
        d = config["dashboard"]
        ws = sh.add_worksheet(title=d["title"], rows=len(d["entries"]) + 8, cols=4)
        values, r = plan_dashboard(ws.id, d.get("subtitle", {}), d["entries"])
        ws.append_rows(values, value_input_option="USER_ENTERED")
        reqs += r
    for t in config.get("tabs", []):
        values = table_values(_records(t["df"]), t["cols"], set(t.get("numeric", [])))
        ws = sh.add_worksheet(title=t["title"], rows=len(values) + 10, cols=len(t["cols"]) + 2)
        ws.append_rows(values, value_input_option="USER_ENTERED")
        reqs += plan_data_tab(ws.id, values, t.get("widths"), t.get("cf"))
    for rt in config.get("raw_tabs", []):
        ncols = max(len(r) for r in rt["values"])
        ws = sh.add_worksheet(title=rt["title"], rows=len(rt["values"]) + 6, cols=ncols + 1)
        ws.append_rows(rt["values"], value_input_option="USER_ENTERED")
        reqs += plan_raw_tab(ws.id, rt["values"], rt.get("widths"), rt.get("header", True),
                             rt.get("row_colors"), rt.get("bold_rows"))
    if reqs:
        sh.batch_update({"requests": reqs})
    sh.del_worksheet(placeholder)
    if not key and config.get("share") == "anyone_reader":
        sh.share(None, perm_type="anyone", role="reader")
    return sh.url, [w.title for w in sh.worksheets()]
