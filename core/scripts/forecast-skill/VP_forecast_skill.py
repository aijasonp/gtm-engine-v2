#!/usr/bin/env python3
"""VP forecast skill mechanics for the {{COMPANY}} Weekly Forecast tracker.

Deterministic helpers so the DM conversation (run by the GTM agent per
references/forecast-skill-vp.md) never does date/math/sheet logic in its head.
Same mechanics as AE_forecast_skill.py; this copy is role-scoped to the VP
({{AE_1}}): team-level call against his $1M quota, Friday reminder, and
his calls never roll into the AE roll-up.

Commands:
  week     [--date YYYY-MM-DD]                forecast-week math for a PT date
  parse    --input TEXT                       parse a dollar answer -> whole dollars
  resolve  --slack-id U...                    Slack user -> roster identity
  last     --name NAME                        submitter's latest Forecast Log row
  team     [--date YYYY-MM-DD]                AE roll-up: each AE's latest call
                                              for the forecast week (VP review)
  opener   --name NAME                        print the Thursday opener DM text
  append   --name NAME --commit N --best-case N --pipeline N
           [--notes T] [--current-state T]    append one Forecast Log row

Env:
  FORECAST_SHEET_ID  overrides the live tracker id (for scratch-sheet tests).
  SLACK_BOT_TOKEN / HUBSPOT_TOKEN read from ~/.openclaw/.env if not set.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

LIVE_SHEET = "REDACTED_GOOGLE_ID"
SHEET_ID = os.environ.get("FORECAST_SHEET_ID", LIVE_SHEET)
PT = ZoneInfo("America/Los_Angeles")
SERIAL_EPOCH = datetime(1899, 12, 30)

# python weekday (Mon=0..Sun=6) -> days to add to reach the Friday that labels
# the Tue-Mon forecast week CONTAINING that date. Monday belongs to the week
# that just ended (previous Friday).
_FRIDAY_OFFSET = {0: -3, 1: 3, 2: 2, 3: 1, 4: 0, 5: -1, 6: -2}


def _load_env():
    path = os.path.expanduser("~/.openclaw/.env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _sheets_values(range_, render="FORMATTED_VALUE"):
    params = {"spreadsheetId": SHEET_ID, "range": range_}
    if render != "FORMATTED_VALUE":
        params["valueRenderOption"] = render
    r = subprocess.run(
        ["gwsg", "sheets", "spreadsheets", "values", "get", "--params", json.dumps(params)],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"sheets values get failed for {range_}: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout).get("values", [])


def _serial_to_date(n):
    return (SERIAL_EPOCH + timedelta(days=float(n))).date()


def _date_to_serial(d):
    if isinstance(d, datetime):
        return (d.replace(tzinfo=None) - SERIAL_EPOCH).total_seconds() / 86400.0
    return (datetime(d.year, d.month, d.day) - SERIAL_EPOCH).days


def forecast_friday(d):
    return d + timedelta(days=_FRIDAY_OFFSET[d.weekday()])


def quarter_label(d):
    return f"Q{(d.month - 1) // 3 + 1} FY{d.year % 100}"


def roster():
    rows = _sheets_values("Quarter Reference!A31:F40", "UNFORMATTED_VALUE")
    out = []
    for row in rows:
        if len(row) >= 3 and row[0] and row[2] in ("AE", "VP", "CRO"):
            out.append({
                "name": row[0],
                "owner_id": int(row[1]) if len(row) > 1 and row[1] != "" else None,
                "role": row[2],
                "quota": row[4] if len(row) > 4 else None,
            })
    return out


def active_weeks():
    rows = _sheets_values("Quarter Reference!B13:B26", "UNFORMATTED_VALUE")
    return {_serial_to_date(r[0]) for r in rows if r and isinstance(r[0], (int, float))}


def cmd_week(args):
    d = date.fromisoformat(args.date) if args.date else datetime.now(PT).date()
    fri = forecast_friday(d)
    weeks = active_weeks()
    print(json.dumps({
        "date": d.isoformat(),
        "friday": fri.isoformat(),
        "week_start": (fri - timedelta(days=3)).isoformat(),
        "week_end": (fri + timedelta(days=3)).isoformat(),
        "quarter_label": quarter_label(fri),
        "in_active_quarter": fri in weeks,
    }))
    return 0


def cmd_parse(args):
    raw = args.input.strip().lower()
    if raw in ("", "none", "n/a", "na", "skip"):
        print(json.dumps({"ok": True, "dollars": 0}))
        return 0
    s = raw.replace("$", "").replace(",", "").replace(" ", "")
    mult = 1
    if s.endswith("k"):
        mult, s = 1_000, s[:-1]
    elif s.endswith("m"):
        mult, s = 1_000_000, s[:-1]
    try:
        val = float(s) * mult
    except ValueError:
        print(json.dumps({"ok": False, "error": f"could not parse {args.input!r} as a dollar amount"}))
        return 1
    if val < 0:
        print(json.dumps({"ok": False, "error": "negative numbers are not allowed"}))
        return 1
    print(json.dumps({"ok": True, "dollars": int(round(val))}))
    return 0


_MONEY_RE = re.compile(r"\$?\s?(\d[\d,]*(?:\.\d+)?)\s*([kKmM])?\b")
_WORD_ZERO_RE = re.compile(r"(?i)\b(none|zero|n/?a)\b")
_CS_MARKER_RE = re.compile(r"(?i)\bcurrent\s*state\b\s*[:\-–—]?\s*")
_NOTES_MARKER_RE = re.compile(r"(?i)\bnotes?\b\s*[:\-–—]?\s*")
_LABEL_BEFORE_NUM_RE = re.compile(
    r"(?i)\b(?:commit|best\s*case|pipeline)\b\s*[:=\-–—]?\s*(?=\$?\s*(?:\d|none\b|zero\b|n/?a\b))")


def _money_token_value(num, suffix):
    s = num.replace(",", "")
    mult = 1
    if suffix:
        mult = 1_000 if suffix.lower() == "k" else 1_000_000
    try:
        return float(s) * mult
    except ValueError:
        return None


def cmd_parse_call(args):
    """Parse a single-message weekly call ({{REVOPS_1}} rule, 2026-10-05): the first
    three dollar amounts IN TEXT ORDER are Commit, Best Case, Pipeline. The
    remaining text is split into Current State and Notes by 'current state:'
    / 'notes:' markers; with no markers, all remaining text goes to Notes
    (Current State stays blank and the completeness-reminder rule applies).
    ALWAYS show the parsed summary and get an explicit confirm before append."""
    text = _LABEL_BEFORE_NUM_RE.sub("", args.input.strip())
    candidates = []
    for m in _MONEY_RE.finditer(text):
        v = _money_token_value(m.group(1), m.group(2))
        if v is not None:
            candidates.append((m.start(), m.span(), v))
    for m in _WORD_ZERO_RE.finditer(text):
        if not any(s <= m.start() < e for _, (s, e), _ in candidates):
            candidates.append((m.start(), m.span(), 0.0))
    candidates.sort(key=lambda c: c[0])
    picked = candidates[:3]
    if len(picked) < 3:
        print(json.dumps({
            "ok": False,
            "error": f"found only {len(picked)} of 3 dollar amounts — need Commit, Best Case, Pipeline in that order",
            "parsed_so_far": [int(round(v)) for _, _, v in picked],
        }))
        return 1
    values = [v for _, _, v in picked]
    if any(v < 0 for v in values):
        print(json.dumps({"ok": False, "error": "negative numbers are not allowed"}))
        return 1
    spans = sorted(s for _, s, _ in picked)
    parts, prev = [], 0
    for s, e in spans:
        parts.append(text[prev:s])
        prev = e
    parts.append(text[prev:])
    residual = " ".join("".join(parts).split())
    cs_m = _CS_MARKER_RE.search(residual)
    nt_m = _NOTES_MARKER_RE.search(residual)
    current_state, notes = "", ""
    if cs_m and nt_m:
        if cs_m.start() < nt_m.start():
            pre = residual[: cs_m.start()].strip(" .;,")
            current_state = residual[cs_m.end(): nt_m.start()].strip(" .;,")
            notes = residual[nt_m.end():].strip(" .;,")
        else:
            pre = residual[: nt_m.start()].strip(" .;,")
            notes = residual[nt_m.end(): cs_m.start()].strip(" .;,")
            current_state = residual[cs_m.end():].strip(" .;,")
        if pre:
            notes = (pre + " " + notes).strip() if notes else pre
    elif cs_m:
        notes = residual[: cs_m.start()].strip(" .;,")
        current_state = residual[cs_m.end():].strip(" .;,")
    elif nt_m:
        current_state = residual[: nt_m.start()].strip(" .;,")
        notes = residual[nt_m.end():].strip(" .;,")
    else:
        notes = residual
    print(json.dumps({
        "ok": True,
        "commit": int(round(values[0])),
        "best_case": int(round(values[1])),
        "pipeline": int(round(values[2])),
        "current_state": current_state,
        "notes": notes,
    }))
    return 0


def _slack_real_name(user_id):
    """Slack profile real_name. Bot lacks users:read.email, so email is
    unavailable; roster names are exact HubSpot spellings, so a real_name
    match is the identity path and the owner ID comes from the roster."""
    import urllib.request
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    req = urllib.request.Request(
        f"https://slack.com/api/users.info?user={user_id}",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    if not data.get("ok"):
        raise RuntimeError(f"users.info failed: {data.get('error')}")
    prof = data["user"].get("profile", {})
    return prof.get("real_name") or prof.get("display_name") or ""


def _norm(s):
    return " ".join(s.lower().split())


def cmd_resolve(args):
    try:
        real_name = _slack_real_name(args.slack_id)
    except Exception as e:
        print(json.dumps({"ok": False, "reason": f"slack lookup failed: {e}"}))
        return 1
    if not real_name:
        print(json.dumps({"ok": False, "reason": "no real_name on Slack profile"}))
        return 1
    people = roster()
    for person in people:
        if _norm(person["name"]) == _norm(real_name):
            print(json.dumps({"ok": True, "slack_name": real_name, **person}))
            return 0
    print(json.dumps({"ok": False, "reason": f"{real_name!r} is not on the forecast roster (AE/VP/CRO)"}))
    return 1


def _log_rows():
    return _sheets_values("Forecast Log!A2:K2000", "UNFORMATTED_VALUE")


def cmd_last(args):
    best = None
    for row in _log_rows():
        if len(row) >= 9 and row[3] == args.name and isinstance(row[2], (int, float)):
            if best is None or row[2] > best[2]:
                best = row
    if best is None:
        print(json.dumps({"found": False}))
        return 0
    fri = _serial_to_date(best[0])
    submitted = SERIAL_EPOCH + timedelta(days=float(best[2]))
    print(json.dumps({
        "found": True,
        "week": fri.isoformat(),
        "week_start": (fri - timedelta(days=3)).isoformat(),
        "week_end": (fri + timedelta(days=3)).isoformat(),
        "submitted_at": submitted.strftime("%a %b %-d at %-I:%M %p"),
        "commit": best[6], "best_case": best[7], "pipeline": best[8],
        "notes": best[9] if len(best) > 9 else "",
        "current_state": best[10] if len(best) > 10 else "",
    }))
    return 0


def cmd_team(args):
    """Team roll-up for review requests (rule from {{REVOPS_1}}, 2026-10-02): an AE
    reviewing calls gets their own row (`last`); the VP gets his AEs' calls.
    Prints each AE's latest Forecast Log row in the forecast week containing
    --date (default: today PT), who hasn't submitted, and the roll-up totals."""
    d = date.fromisoformat(args.date) if args.date else datetime.now(PT).date()
    fri = forecast_friday(d)
    fri_serial = float(_date_to_serial(fri))
    members = [p for p in roster() if p["role"] == "AE"]
    best_by_name = {}
    for row in _log_rows():
        if len(row) < 9 or not isinstance(row[0], (int, float)) or not isinstance(row[2], (int, float)):
            continue
        if abs(float(row[0]) - fri_serial) > 0.001:
            continue
        prev = best_by_name.get(row[3])
        if prev is None or row[2] > prev[2]:
            best_by_name[row[3]] = row
    out = []
    totals = {"commit": 0, "best_case": 0, "pipeline": 0}
    for m in members:
        row = best_by_name.get(m["name"])
        if row is None:
            out.append({"name": m["name"], "role": m["role"], "submitted": False})
            continue
        submitted = SERIAL_EPOCH + timedelta(days=float(row[2]))
        out.append({
            "name": m["name"], "role": m["role"], "submitted": True,
            "submitted_at": submitted.strftime("%a %b %-d at %-I:%M %p"),
            "commit": row[6], "best_case": row[7], "pipeline": row[8],
            "notes": row[9] if len(row) > 9 else "",
            "current_state": row[10] if len(row) > 10 else "",
        })
        totals["commit"] += int(row[6])
        totals["best_case"] += int(row[7])
        totals["pipeline"] += int(row[8])
    print(json.dumps({
        "week": fri.isoformat(),
        "week_start": (fri - timedelta(days=3)).isoformat(),
        "week_end": (fri + timedelta(days=3)).isoformat(),
        "quarter_label": quarter_label(fri),
        "submitted_count": sum(1 for m in out if m["submitted"]),
        "member_count": len(out),
        "rollup_totals": totals,
        "totals_scope": "AE roll-up (sum of AE rows above)",
        "members": out,
    }))
    return 0


def _money(n):
    return f"${int(round(float(n))):,}"


def cmd_opener(args):
    today = datetime.now(PT).date()
    fri = forecast_friday(today)
    ws, we = fri - timedelta(days=3), fri + timedelta(days=3)
    q = quarter_label(fri)
    week_line = (f"This is your call for the forecast week of "
                 f"{ws.strftime('%a %b %-d')} – {we.strftime('%a %b %-d')}, {q}.")
    rows = _log_rows()
    last = None
    for row in rows:
        if len(row) >= 9 and row[3] == args.name and isinstance(row[2], (int, float)):
            if last is None or row[2] > last[2]:
                last = row
    if last is not None:
        lfri = _serial_to_date(last[0])
        echo = (f"Last week ({lfri.strftime('%b %-d')}) you called: "
                f"Commit {_money(last[6])} · Best Case {_money(last[7])} · Pipeline {_money(last[8])}.")
    else:
        echo = "This is your first call on the new tracker."
    in_q = fri in active_weeks()
    person = next((p for p in roster() if p["name"] == args.name), None)
    quota_txt = f" your {_money(person['quota'])} team quota" if person and person.get("quota") else " your team quota"
    lines = [
        "Weekly forecast time. :chart_with_upwards_trend:",
        week_line,
        echo,
        f"This is your team-level call against{quota_txt} — your own numbers, not the AE roll-up.",
    ]
    if not in_q:
        lines.append(f"(Heads up: this week lands in {q}, outside the active quarter on the tracker.)")
    lines.append("In the following order enter your weekly Commit $, Best Case $, Pipeline $. Add your Current state and Notes (more detailed info). One message is fine — I'll show you what I parsed and confirm before logging. Takes 2 minutes.")
    print("\n".join(lines))
    return 0


def cmd_append(args):
    people = {p["name"]: p for p in roster()}
    person = people.get(args.name)
    if person is None:
        print(json.dumps({"ok": False, "error": f"{args.name!r} is not on the roster (AE/VP/CRO)"}))
        return 1
    for label, v in (("Commit", args.commit), ("Best Case", args.best_case), ("Pipeline", args.pipeline)):
        if v < 0:
            print(json.dumps({"ok": False, "error": f"{label} cannot be negative"}))
            return 1
    now = datetime.now(PT)
    fri = forecast_friday(now.date())
    q = quarter_label(fri)
    row = [
        _date_to_serial(fri),
        q,
        _date_to_serial(now),
        person["name"],
        person["owner_id"],
        person["role"],
        int(args.commit), int(args.best_case), int(args.pipeline),
        args.notes or "",
        args.current_state or "",
    ]
    r = subprocess.run(
        ["gwsg", "sheets", "spreadsheets", "values", "append",
         "--params", json.dumps({
             "spreadsheetId": SHEET_ID,
             "range": "Forecast Log!A1:K1",
             "valueInputOption": "RAW",
             "insertDataOption": "INSERT_ROWS",
         }),
         "--json", json.dumps({"range": "Forecast Log!A1:K1", "majorDimension": "ROWS", "values": [row]})],
        capture_output=True, text=True)
    if r.returncode != 0:
        print(json.dumps({"ok": False, "error": f"sheets append failed: {r.stderr.strip()[:300]}"}))
        return 1
    print(json.dumps({
        "ok": True,
        "friday": fri.isoformat(),
        "week_start": (fri - timedelta(days=3)).isoformat(),
        "week_end": (fri + timedelta(days=3)).isoformat(),
        "quarter_label": q,
        "in_active_quarter": fri in active_weeks(),
        "name": person["name"], "role": person["role"],
        "commit": int(args.commit), "best_case": int(args.best_case), "pipeline": int(args.pipeline),
    }))
    return 0


def main():
    _load_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("week"); p.add_argument("--date"); p.set_defaults(fn=cmd_week)
    p = sub.add_parser("parse"); p.add_argument("--input", required=True); p.set_defaults(fn=cmd_parse)
    p = sub.add_parser("parse-call"); p.add_argument("--input", required=True); p.set_defaults(fn=cmd_parse_call)
    p = sub.add_parser("resolve"); p.add_argument("--slack-id", required=True); p.set_defaults(fn=cmd_resolve)
    p = sub.add_parser("last"); p.add_argument("--name", required=True); p.set_defaults(fn=cmd_last)
    p = sub.add_parser("team"); p.add_argument("--date"); p.set_defaults(fn=cmd_team)
    p = sub.add_parser("opener"); p.add_argument("--name", required=True); p.set_defaults(fn=cmd_opener)
    p = sub.add_parser("append")
    p.add_argument("--name", required=True)
    p.add_argument("--commit", type=float, required=True)
    p.add_argument("--best-case", type=float, required=True)
    p.add_argument("--pipeline", type=float, required=True)
    p.add_argument("--notes", default="")
    p.add_argument("--current-state", default="")
    p.set_defaults(fn=cmd_append)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
