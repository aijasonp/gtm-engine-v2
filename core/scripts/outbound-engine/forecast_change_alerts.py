#!/usr/bin/env python3
"""
forecast_change_alerts.py: HubSpot forecast-change alerting.

Compares the current state of in-quarter new-business/upsell deals against the
previous snapshot and emits per-recipient Slack mrkdwn messages. Recipients,
the AE roster and leadership owner IDs come from a JSON config
(FORECAST_ALERTS_CONFIG, default forecast_alerts.config.json next to this file;
see forecast_alerts.config.example.json). Each recipient has a scope:
"all" (every in-scope deal) or "roster" (AE-roster deals only).

Usage:
    forecast_change_alerts.py [--run-key LABEL] [--dry-run] [--pm-window]

Output: a single JSON object on stdout:
    {"messages": {"<recipient key>": "<mrkdwn or null>", ...},
     "excluded_missing_type_count": N, "in_scope_deal_count": N, "alert_count": N}

On API failure after retries: {"error": "...", "detail": "<raw body>"} and exit 1.
"""

import argparse
import calendar
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

HUBSPOT_BASE = "https://api.hubapi.com"
TOKEN = os.environ.get("HUBSPOT_TOKEN")

STATE_DIR = Path(__file__).resolve().parent / "state"
STATE_FILE = STATE_DIR / "forecast-alert-snapshots.json"

TZ = ZoneInfo("America/Los_Angeles")

DEAL_PROPERTIES = [
    "dealname",
    "dealtype",
    "amount",
    "closedate",
    "hs_manual_forecast_category",
    "dealstage",
    "hubspot_owner_id",
]

HISTORY_PROPERTIES = [
    "hs_manual_forecast_category",
    "closedate",
    "amount",
    "dealstage",
]

IN_SCOPE_DEALTYPES = {"newbusiness", "Upsell"}
IN_SCOPE_FORECAST = {"BEST_CASE", "COMMIT"}

FORECAST_LABELS = {
    "OMIT": "Not forecasted",
    "PIPELINE": "Pipeline",
    "BEST_CASE": "Best case",
    "COMMIT": "Commit",
    "CLOSED": "Closed won",
}

DEALTYPE_LABELS = {
    "newbusiness": "New Business",
    "Upsell": "Upsell",
}

# Owner routing (from config)
CONFIG_FILE = Path(os.environ.get(
    "FORECAST_ALERTS_CONFIG",
    Path(__file__).resolve().parent / "forecast_alerts.config.json",
))


def load_routing():
    """Return (ae_roster, leadership_ids, recipients) from the config file."""
    if not CONFIG_FILE.exists():
        raise SystemExit(json.dumps({
            "error": f"missing config {CONFIG_FILE}; copy forecast_alerts.config.example.json",
            "detail": "",
        }))
    cfg = json.loads(CONFIG_FILE.read_text())
    roster = {str(x) for x in cfg.get("ae_roster_owner_ids", [])}
    leaders = {str(x) for x in cfg.get("leadership_owner_ids", [])}
    recipients = cfg.get("recipients", [])
    for r in recipients:
        if r.get("scope") not in ("all", "roster"):
            raise SystemExit(json.dumps({"error": f"recipient {r.get('key')} needs scope all or roster", "detail": ""}))
    return roster, leaders, recipients


AE_ROSTER, LEADERSHIP_IDS, RECIPIENTS = set(), set(), []

# Trigger severities
URGENT = "urgent"
WATCH = "watch"
GOOD = "good"

# Watch thresholds
PUSH_DAYS_WATCH = 14
AMOUNT_DROP_WATCH_PCT = 20.0


# --------------------------------------------------------------------------
# HubSpot client with retries
# --------------------------------------------------------------------------

class HubSpotError(Exception):
    def __init__(self, msg, detail=""):
        super().__init__(msg)
        self.detail = detail


def hs_request(method, path, *, params=None, json_body=None, retries=3):
    """HubSpot request with retry/backoff. Raises HubSpotError after final failure."""
    if not TOKEN:
        raise HubSpotError("HUBSPOT_TOKEN not set in environment")
    url = f"{HUBSPOT_BASE}{path}"
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    backoff = 2
    last_err = None
    last_body = ""
    for attempt in range(retries):
        try:
            resp = requests.request(
                method, url, headers=headers, params=params, json=json_body, timeout=30
            )
        except requests.RequestException as e:
            last_err = f"network error: {e}"
            last_body = ""
            time.sleep(backoff)
            backoff *= 2
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            last_err = f"HTTP {resp.status_code}"
            last_body = resp.text
            # Respect Retry-After when present
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else backoff
            time.sleep(wait)
            backoff *= 2
            continue
        if resp.status_code >= 400:
            # 4xx (non-429): fail immediately with raw body
            raise HubSpotError(f"HTTP {resp.status_code} on {method} {path}", detail=resp.text)
        try:
            return resp.json()
        except ValueError:
            raise HubSpotError(
                f"Non-JSON response on {method} {path}", detail=resp.text
            )
    raise HubSpotError(
        f"Exhausted retries on {method} {path}: {last_err}", detail=last_body
    )


def get_portal_id():
    d = hs_request("GET", "/account-info/v3/details")
    return str(d["portalId"])


def get_owners():
    """Full owner list: id -> display name."""
    owners = {}
    after = None
    while True:
        params = {"limit": 100}
        if after:
            params["after"] = after
        d = hs_request("GET", "/crm/v3/owners", params=params)
        for o in d.get("results", []):
            fn = (o.get("firstName") or "").strip()
            ln = (o.get("lastName") or "").strip()
            name = (fn + " " + ln).strip()
            if not name:
                name = o.get("email") or f"Owner {o['id']}"
            owners[str(o["id"])] = name
        paging = d.get("paging", {})
        nxt = paging.get("next", {}).get("after")
        if not nxt:
            break
        after = nxt
    return owners


def search_current_quarter_deals(q_start_ms, q_end_ms):
    """Paginated search for deals with closedate within the current quarter."""
    deals = {}
    after = None
    while True:
        body = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "closedate",
                            "operator": "GTE",
                            "value": str(q_start_ms),
                        },
                        {
                            "propertyName": "closedate",
                            "operator": "LTE",
                            "value": str(q_end_ms),
                        },
                    ]
                }
            ],
            "properties": DEAL_PROPERTIES,
            "limit": 100,
        }
        if after:
            body["after"] = after
        d = hs_request("POST", "/crm/v3/objects/deals/search", json_body=body)
        for r in d.get("results", []):
            deals[r["id"]] = r.get("properties", {})
        paging = d.get("paging", {})
        nxt = paging.get("next", {}).get("after")
        if not nxt:
            break
        after = nxt
    return deals


def batch_read_deals(deal_ids):
    """Batch read deals by ID. Returns {id: properties}."""
    out = {}
    if not deal_ids:
        return out
    # HubSpot batch read limit is 100 inputs per call
    ids = list(deal_ids)
    for i in range(0, len(ids), 100):
        chunk = ids[i : i + 100]
        body = {
            "properties": DEAL_PROPERTIES,
            "inputs": [{"id": str(x)} for x in chunk],
        }
        d = hs_request("POST", "/crm/v3/objects/deals/batch/read", json_body=body)
        for r in d.get("results", []):
            out[r["id"]] = r.get("properties", {})
    return out


def get_deal_with_history(deal_id):
    """Single deal with property history for history_properties."""
    props = ",".join(DEAL_PROPERTIES)
    hist = ",".join(HISTORY_PROPERTIES)
    d = hs_request(
        "GET",
        f"/crm/v3/objects/deals/{deal_id}",
        params={"properties": props, "propertiesWithHistory": hist},
    )
    return d.get("properties", {}), d.get("propertiesWithHistory", {})


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def quarter_bounds(now):
    """Return (quarter_number, year, start_datetime, end_datetime) for the quarter containing `now`."""
    q = (now.month - 1) // 3 + 1
    start_month = 3 * (q - 1) + 1
    end_month = 3 * q
    start = dt.datetime(now.year, start_month, 1, 0, 0, 0, tzinfo=TZ)
    last_day = calendar.monthrange(now.year, end_month)[1]
    end = dt.datetime(now.year, end_month, last_day, 23, 59, 59, tzinfo=TZ)
    return q, now.year, start, end


def in_final_3_weeks(now, q_end):
    """True if today is within the final 21 days of the quarter (inclusive)."""
    days_left = (q_end.date() - now.date()).days
    return 0 <= days_left <= 20  # 21 calendar days inclusive of quarter-end day


def parse_closedate(value):
    """Parse HubSpot closedate to a date (America/Los_Angeles). None if missing."""
    if not value:
        return None
    try:
        if value.endswith("Z"):
            t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            t = dt.datetime.fromisoformat(value)
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
        return t.astimezone(TZ).date()
    except (ValueError, AttributeError):
        return None


def fmt_amount(a):
    if a is None:
        return "$0"
    return f"${a:,.0f}"


def fmt_forecast(v):
    if not v:
        return "(blank)"
    return FORECAST_LABELS.get(v, v)


def fmt_dealtype(v):
    return DEALTYPE_LABELS.get(v, v or "(missing)")


def is_closed_lost_stage(dealstage):
    return bool(dealstage) and "closedlost" in dealstage.lower()


def is_closed_won_stage(dealstage):
    return bool(dealstage) and "closedwon" in dealstage.lower()


def is_closed_won(props):
    cat = (props.get("hs_manual_forecast_category") or "").upper()
    if cat == "CLOSED":
        return True
    return is_closed_won_stage(props.get("dealstage") or "")


def is_closed_lost(props):
    return is_closed_lost_stage(props.get("dealstage") or "")


def to_float(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def normalize_deal_record(deal_id, props, owners):
    """Convert HubSpot properties to the snapshot record shape."""
    owner_id = str(props.get("hubspot_owner_id") or "")
    closedate_d = parse_closedate(props.get("closedate") or "")
    return {
        "id": str(deal_id),
        "name": props.get("dealname") or f"Deal {deal_id}",
        "owner_id": owner_id,
        "owner_name": owners.get(owner_id, f"Owner {owner_id}" if owner_id else "Unassigned"),
        "dealtype": props.get("dealtype") or "",
        "amount": to_float(props.get("amount")),
        "forecast_category": props.get("hs_manual_forecast_category") or "",
        "closedate": closedate_d.isoformat() if closedate_d else None,
        "dealstage": props.get("dealstage") or "",
    }


def value_as_of(history_entries, cutoff_dt):
    """Walk property history (newest-first list from HubSpot) and return the value
    as of cutoff_dt. History entries are dicts with 'value' and 'timestamp' (UTC ISO).
    Returns None if nothing at/before cutoff."""
    if not history_entries:
        return None
    # HubSpot returns newest first; find the newest entry with timestamp <= cutoff
    for entry in history_entries:
        ts = entry.get("timestamp")
        if not ts:
            continue
        try:
            t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if t <= cutoff_dt:
            return entry.get("value")
    return None


# --------------------------------------------------------------------------
# State / snapshots
# --------------------------------------------------------------------------

def load_state():
    if not STATE_FILE.exists():
        return {"snapshots": {}}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"snapshots": {}}


def save_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(STATE_FILE)


def most_recent_snapshot(state, exclude_key=None):
    """Return (key, snapshot_dict) for most recent entry by run_at, excluding exclude_key."""
    snaps = state.get("snapshots", {})
    best_key, best = None, None
    for k, s in snaps.items():
        if exclude_key and k == exclude_key:
            continue
        if best is None or s.get("run_at", "") > best.get("run_at", ""):
            best_key, best = k, s
    return best_key, best


# --------------------------------------------------------------------------
# Change detection
# --------------------------------------------------------------------------

def classify_deal_changes(prev, curr, q_end_date):
    """
    Compare prev snapshot record vs curr snapshot record.
    Returns (severity, [change_strings]) or (None, []) if no alert.

    prev / curr fields: forecast_category, closedate (YYYY-MM-DD), amount (float),
    dealstage, dealtype.

    Both prev and curr are in-scope by the caller.
    """
    changes = []  # list of (severity, string)
    prev_cat = (prev.get("forecast_category") or "").upper()
    curr_cat = (curr.get("forecast_category") or "").upper()

    prev_closed_lost = is_closed_lost_stage(prev.get("dealstage") or "")
    curr_closed_lost = is_closed_lost_stage(curr.get("dealstage") or "")
    prev_closed_won = (prev_cat == "CLOSED") or is_closed_won_stage(prev.get("dealstage") or "")
    curr_closed_won = (curr_cat == "CLOSED") or is_closed_won_stage(curr.get("dealstage") or "")

    prev_in_q = prev.get("closedate_in_quarter", True)
    curr_in_q = curr.get("closedate_in_quarter", True)

    # --- Forecast / stage transitions -------------------------------------
    forecast_sev = None
    forecast_str = None

    if curr_closed_won and not prev_closed_won:
        if prev_cat in ("BEST_CASE", "COMMIT"):
            forecast_sev = GOOD
            forecast_str = "Closed Won"
    elif curr_closed_lost and not prev_closed_lost:
        if prev_cat == "COMMIT":
            forecast_sev = URGENT
            forecast_str = "Closed Lost"
        elif prev_cat == "BEST_CASE":
            forecast_sev = WATCH
            forecast_str = "Closed Lost"
    elif prev_cat != curr_cat and prev_cat in ("BEST_CASE", "COMMIT") and curr_cat in (
        "OMIT",
        "PIPELINE",
        "BEST_CASE",
        "COMMIT",
    ):
        # Category-to-category transitions
        if prev_cat == "COMMIT" and curr_cat in ("BEST_CASE", "PIPELINE", "OMIT"):
            forecast_sev = URGENT
            forecast_str = f"Forecast: {fmt_forecast(prev_cat)} → {fmt_forecast(curr_cat)}"
        elif prev_cat == "BEST_CASE" and curr_cat in ("PIPELINE", "OMIT"):
            forecast_sev = WATCH
            forecast_str = f"Forecast: {fmt_forecast(prev_cat)} → {fmt_forecast(curr_cat)}"
        elif prev_cat == "BEST_CASE" and curr_cat == "COMMIT":
            forecast_sev = GOOD
            forecast_str = f"Forecast: {fmt_forecast(prev_cat)} → {fmt_forecast(curr_cat)}"
        # COMMIT -> COMMIT etc: no alert
        # COMMIT -> PIPELINE handled above
    if forecast_str:
        changes.append((forecast_sev, forecast_str))

    # --- Close-date moves ---------------------------------------------------
    prev_cd = prev.get("closedate")
    curr_cd = curr.get("closedate")
    if prev_cd and curr_cd and prev_cd != curr_cd and not curr_closed_won and not curr_closed_lost:
        prev_d = dt.date.fromisoformat(prev_cd)
        curr_d = dt.date.fromisoformat(curr_cd)
        delta_days = (curr_d - prev_d).days  # positive = pushed later
        if delta_days > 0:  # only alert on pushes (later), not pulls (earlier)
            pushed_out = prev_in_q and not curr_in_q
            if pushed_out:
                if prev_cat == "COMMIT":
                    sev = URGENT
                elif prev_cat == "BEST_CASE":
                    sev = WATCH
                else:
                    sev = None
                if sev:
                    q_label = f"Q{(q_end_date.month - 1) // 3 + 1}"
                    changes.append(
                        (sev, f"Close date: {prev_cd} → {curr_cd} (out of {q_label})")
                    )
            elif curr_in_q and prev_in_q:
                # Within-quarter push
                days_to_q_end = (q_end_date - curr_d).days
                into_final = days_to_q_end <= 13  # final 14 days inclusive
                if delta_days >= PUSH_DAYS_WATCH or into_final:
                    base = f"Close date: {prev_cd} → {curr_cd} (pushed {delta_days} days)"
                    if into_final:
                        base += " (into final 2 weeks)"
                    changes.append((WATCH, base))

    # --- Amount decreases ----------------------------------------------------
    prev_amt = prev.get("amount")
    curr_amt = curr.get("amount")
    if (
        prev_amt
        and curr_amt is not None
        and prev_cat == "COMMIT"
        and curr_cat == "COMMIT"
        and not curr_closed_won
        and not curr_closed_lost
        and curr_amt < prev_amt
    ):
        drop_pct = (prev_amt - curr_amt) / prev_amt * 100.0
        if drop_pct >= AMOUNT_DROP_WATCH_PCT:
            changes.append(
                (
                    WATCH,
                    f"Amount: {fmt_amount(prev_amt)} → {fmt_amount(curr_amt)} (-{drop_pct:.0f}%)",
                )
            )

    if not changes:
        return None, []
    # Overall severity = highest among changes (urgent > watch > good)
    order = {URGENT: 0, WATCH: 1, GOOD: 2}
    overall = min((s for s, _ in changes), key=lambda s: order[s])
    return overall, [s for _, s in changes]


# --------------------------------------------------------------------------
# Message rendering
# --------------------------------------------------------------------------

def deal_url(portal_id, deal_id):
    return f"https://app.hubspot.com/contacts/{portal_id}/deal/{deal_id}"


def render_deal_line(portal_id, deal, change_str, tag=None):
    link = f"<{deal_url(portal_id, deal['id'])}|{deal['name']}>"
    dtype = fmt_dealtype(deal.get("dealtype") or "")
    amt = fmt_amount(deal.get("amount"))
    line = f"{link} | {deal['owner_name']} | {dtype} | {amt} | {change_str}"
    if tag:
        line += f" ({tag})"
    return line


def render_message(portal_id, header_label, urgent, watch, good, footer_lines=None):
    """urgent/watch/good: lists of (deal, change_str, tag) tuples sorted by amount desc."""
    if not urgent and not watch and not good:
        return None
    today_str = dt.datetime.now(TZ).strftime("%a, %b %-d")
    lines = [f"*Forecast Changes: {today_str} | {header_label}*", ""]

    def section(emoji, title, items):
        if not items:
            return
        lines.append(f"{emoji} *{title}*")
        items_sorted = sorted(items, key=lambda x: (x[0].get("amount") or 0), reverse=True)
        for deal, change, tag in items_sorted:
            lines.append(render_deal_line(portal_id, deal, change, tag=tag))
        lines.append("")

    section("🔴", "Urgent", urgent)
    section("🟡", "Watch", watch)
    section("🟢", "Good News", good)

    if footer_lines:
        for fl in footer_lines:
            lines.append(fl)

    return "\n".join(lines).rstrip()


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    global AE_ROSTER, LEADERSHIP_IDS, RECIPIENTS
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-key", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pm-window", action="store_true")
    args = parser.parse_args()
    AE_ROSTER, LEADERSHIP_IDS, RECIPIENTS = load_routing()

    now = dt.datetime.now(TZ)
    q, q_year, q_start, q_end = quarter_bounds(now)
    q_start_ms = int(q_start.timestamp() * 1000)
    q_end_ms = int(q_end.timestamp() * 1000)
    q_end_date = q_end.date()

    run_key = args.run_key or now.strftime("%Y%m%dT%H%M%S")

    # --pm-window gate: only run in final 3 weeks of quarter
    if args.pm_window and not in_final_3_weeks(now, q_end):
        print(json.dumps({"skipped": "outside final 3 weeks"}))
        return 0

    try:
        portal_id = get_portal_id()
        owners = get_owners()
        current_props = search_current_quarter_deals(q_start_ms, q_end_ms)
    except HubSpotError as e:
        print(json.dumps({"error": str(e), "detail": e.detail}))
        return 1

    # Load state and previous snapshot
    state = load_state()
    prev_key, prev_snap = most_recent_snapshot(state, exclude_key=run_key)

    # Detect quarter rollover: previous snapshot was taken in a different quarter
    quarter_rollover = False
    if prev_snap:
        prev_q = prev_snap.get("quarter")
        prev_year = prev_snap.get("year")
        if prev_q is not None and (prev_q != q or prev_year != q_year):
            quarter_rollover = True

    previous_records = (prev_snap or {}).get("deals", {}) if prev_snap else {}

    # Identify prior-snapshot deals no longer in the current-quarter search
    missing_ids = [did for did in previous_records.keys() if did not in current_props]
    if missing_ids:
        try:
            missing_props = batch_read_deals(missing_ids)
        except HubSpotError as e:
            print(json.dumps({"error": str(e), "detail": e.detail}))
            return 1
        current_props.update(missing_props)

    # Build current snapshot records for every deal we know about
    current_records = {}
    for did, props in current_props.items():
        rec = normalize_deal_record(did, props, owners)
        cd = parse_closedate(props.get("closedate") or "")
        rec["closedate_in_quarter"] = bool(cd and q_start.date() <= cd <= q_end_date)
        current_records[did] = rec

    # Cold start / quarter rollover: rebuild "previous" from 24h property history
    use_history_for_previous = quarter_rollover or prev_snap is None
    if use_history_for_previous:
        cutoff = now - dt.timedelta(hours=24)
        cutoff_utc = cutoff.astimezone(dt.timezone.utc)
        rebuilt_prev = {}
        for did, curr_rec in current_records.items():
            try:
                props, hist = get_deal_with_history(did)
            except HubSpotError as e:
                print(json.dumps({"error": str(e), "detail": e.detail}))
                return 1
            prev_cat = value_as_of(hist.get("hs_manual_forecast_category"), cutoff_utc)
            prev_cd_raw = value_as_of(hist.get("closedate"), cutoff_utc)
            prev_amt_raw = value_as_of(hist.get("amount"), cutoff_utc)
            prev_stage = value_as_of(hist.get("dealstage"), cutoff_utc)
            prev_cd_d = parse_closedate(prev_cd_raw) if prev_cd_raw else None
            rebuilt_prev[did] = {
                "id": did,
                "name": curr_rec["name"],
                "owner_id": curr_rec["owner_id"],
                "owner_name": curr_rec["owner_name"],
                "dealtype": curr_rec["dealtype"],
                "amount": to_float(prev_amt_raw),
                "forecast_category": prev_cat or "",
                "closedate": prev_cd_d.isoformat() if prev_cd_d else None,
                "dealstage": prev_stage or "",
                "closedate_in_quarter": bool(
                    prev_cd_d and q_start.date() <= prev_cd_d <= q_end_date
                ),
            }
        previous_records = rebuilt_prev

    # ---- Scope classification ---------------------------------------------
    in_scope = {}          # did -> (prev_rec_or_None, curr_rec)
    excluded_missing_type = []  # curr_rec list
    for did, curr in current_records.items():
        prev = previous_records.get(did)
        dtype = curr.get("dealtype") or ""

        curr_in_q = curr.get("closedate_in_quarter", False)
        prev_in_q = prev.get("closedate_in_quarter", False) if prev else False
        curr_cat = (curr.get("forecast_category") or "").upper()
        prev_cat = (prev.get("forecast_category") or "").upper() if prev else ""

        # Closed Won / Closed Lost detection for current
        curr_closed_won = is_closed_won(
            {
                "hs_manual_forecast_category": curr_cat,
                "dealstage": curr.get("dealstage") or "",
            }
        )
        curr_closed_lost = is_closed_lost({"dealstage": curr.get("dealstage") or ""})

        # Condition 2: closedate in quarter now or previously
        if not (curr_in_q or prev_in_q):
            continue
        # Condition 3: forecast BEST_CASE/COMMIT now or previously.
        # A closed-won/closed-lost deal whose category got wiped still counts if prev qualified.
        forecast_in_scope = (
            curr_cat in IN_SCOPE_FORECAST
            or prev_cat in IN_SCOPE_FORECAST
        )
        if not forecast_in_scope:
            continue
        # Condition 1: dealtype
        if dtype not in IN_SCOPE_DEALTYPES:
            if dtype == "":
                excluded_missing_type.append(curr)
            # Non-blank wrong-type OR blank: excluded either way (blank collected for footer)
            continue

        in_scope[did] = (prev, curr)

    # ---- Change detection --------------------------------------------------
    alerts = {URGENT: [], WATCH: [], GOOD: []}  # sev -> list of (curr_rec, change_str, tag)
    for did, (prev, curr) in in_scope.items():
        if prev is None:
            # No baseline available (should not happen; cold start rebuilds prev), skip
            continue
        # Skip if nothing relevant changed at all (cheap equality check first)
        sev, change_strs = classify_deal_changes(prev, curr, q_end_date)
        if not sev:
            continue
        tag = None
        if curr["owner_id"] not in AE_ROSTER and curr["owner_id"] not in LEADERSHIP_IDS:
            tag = "Unassigned team"
        alerts[sev].append((curr, "; ".join(change_strs), tag))

    alert_count = sum(len(v) for v in alerts.values())

    # ---- Routing -----------------------------------------------------------
    routed = {}
    for r in RECIPIENTS:
        bucket = {URGENT: [], WATCH: [], GOOD: []}
        for sev, items in alerts.items():
            for deal, change, tag in items:
                if r["scope"] == "all":
                    bucket[sev].append((deal, change, tag))
                elif deal["owner_id"] in AE_ROSTER:
                    bucket[sev].append((deal, change, None))
        routed[r["key"]] = bucket

    missing_type_footer = []
    for rec in excluded_missing_type:
        link = f"<{deal_url(portal_id, rec['id'])}|{rec['name']}>"
        missing_type_footer.append(f"Excluded, missing deal type: {link}")

    messages = {}
    for r in RECIPIENTS:
        b = routed[r["key"]]
        has_any = bool(b[URGENT] or b[WATCH] or b[GOOD])
        messages[r["key"]] = render_message(
            portal_id,
            r.get("title") or ("All Teams" if r["scope"] == "all" else "Account Executives"),
            b[URGENT],
            b[WATCH],
            b[GOOD],
            footer_lines=missing_type_footer if (r.get("show_missing_type_footer") and has_any) else None,
        )

    # ---- Snapshot write ----------------------------------------------------
    if not args.dry_run:
        snap = {
            "run_at": now.isoformat(),
            "quarter": q,
            "year": q_year,
            "deals": {did: curr for did, curr in current_records.items()},
        }
        state.setdefault("snapshots", {})[run_key] = snap
        try:
            save_state(state)
        except OSError as e:
            print(json.dumps({"error": f"failed to write state: {e}", "detail": ""}))
            return 1

    payload = {
        "messages": messages,
        "excluded_missing_type_count": len(excluded_missing_type),
        "in_scope_deal_count": len(in_scope),
        "alert_count": alert_count,
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
