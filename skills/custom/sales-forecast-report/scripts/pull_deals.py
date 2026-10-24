#!/usr/bin/env python3
"""Pull open HubSpot deals with context for the weekly sales forecast report."""
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

HUBSPOT_BASE = "https://api.hubapi.com"
DEAL_PROPERTIES = (
    "dealname,amount,closedate,dealstage,pipeline,hubspot_owner_id,"
    "hs_lastmodifieddate,notes_last_updated,createdate,description,"
    "hs_priority,hs_deal_stage_probability,num_associated_contacts"
)
ASSOCIATIONS = "contacts,companies,engagements"


def load_env_token() -> str:
    token = os.environ.get("HUBSPOT_TOKEN")
    if token:
        return token.strip()

    env_path = Path(os.path.expanduser(os.environ.get("GTM_ENV_FILE", "~/.gtm/.env")))
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

    token = os.environ.get("HUBSPOT_TOKEN")
    if not token:
        print("[ERROR] HUBSPOT_TOKEN is not set", file=sys.stderr)
        sys.exit(1)
    return token.strip()


def request_json(method: str, url: str, token: str, **kwargs) -> Dict[str, Any]:
    headers = kwargs.pop("headers", {})
    headers.update({"Authorization": f"Bearer {token}"})
    resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    if not resp.ok:
        print(
            f"[ERROR] HubSpot API {method} {url} failed: {resp.status_code} {resp.text}",
            file=sys.stderr,
        )
        sys.exit(1)
    return resp.json()


def parse_hs_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)

    value = str(value).strip()
    if not value:
        return None
    if value.isdigit():
        return datetime.fromtimestamp(int(value) / 1000.0, tz=timezone.utc)

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def isoformat(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def compute_week_label(today_val: Optional[date] = None) -> str:
    today_val = today_val or date.today()
    monday = today_val - timedelta(days=today_val.weekday())
    sunday = monday + timedelta(days=6)

    def fmt_day(d: date) -> str:
        return f"{d.strftime('%b')} {d.day}"

    if monday.year == sunday.year:
        return f"Week of {fmt_day(monday)} - {fmt_day(sunday)}, {sunday.year}"
    return (
        f"Week of {fmt_day(monday)}, {monday.year} - "
        f"{fmt_day(sunday)}, {sunday.year}"
    )


def fetch_all_deals(token: str) -> List[Dict[str, Any]]:
    deals = []
    url = f"{HUBSPOT_BASE}/crm/v3/objects/deals"
    params = {
        "limit": 100,
        "archived": "false",
        "properties": DEAL_PROPERTIES,
        "associations": ASSOCIATIONS,
    }

    while url:
        data = request_json("GET", url, token, params=params)
        deals.extend(data.get("results", []))
        paging = data.get("paging", {})
        next_link = paging.get("next", {}).get("link")
        url = next_link
        params = None  # already included in link for next pages
    return deals


def fetch_owners(token: str) -> Dict[str, Dict[str, str]]:
    owners = {}
    url = f"{HUBSPOT_BASE}/crm/v3/owners"
    params = {"limit": 100}
    while url:
        try:
            data = request_json("GET", url, token, params=params)
        except SystemExit:
            print(
                "[WARN] Failed to fetch owners (missing crm.objects.owners.read scope?). "
                "Continuing without owner map.",
                file=sys.stderr,
            )
            return {}
        for owner in data.get("results", []):
            first = (owner.get("firstName") or "").strip()
            last = (owner.get("lastName") or "").strip()
            full_name = " ".join(part for part in [first, last] if part).strip()
            if not full_name:
                full_name = owner.get("email") or f"Owner {owner.get('id')}"
            owners[str(owner.get("id"))] = {
                "name": full_name,
                "email": owner.get("email"),
            }
        paging = data.get("paging", {})
        url = paging.get("next", {}).get("link")
        params = None
    return owners


def fetch_association_ids(token: str, deal_id: str, object_type: str, limit: int) -> List[str]:
    url = f"{HUBSPOT_BASE}/crm/v4/objects/deals/{deal_id}/associations/{object_type}"
    params = {"limit": limit}
    data = request_json("GET", url, token, params=params)
    ids = []
    for item in data.get("results", []):
        to_object_id = item.get("toObjectId") or item.get("id")
        if to_object_id:
            ids.append(str(to_object_id))
    return ids[:limit]


def fetch_engagement(token: str, engagement_id: str) -> Optional[Dict[str, Any]]:
    url = f"{HUBSPOT_BASE}/crm/v3/objects/engagements/{engagement_id}"
    params = {
        "properties": "hs_engagement_type,hs_timestamp,hs_body_preview,hs_email_subject",
    }
    try:
        data = request_json("GET", url, token, params=params)
        return data
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[WARN] Failed to fetch engagement {engagement_id}: {exc}", file=sys.stderr)
        return None


def fetch_note(token: str, note_id: str) -> Optional[Dict[str, Any]]:
    url = f"{HUBSPOT_BASE}/crm/v3/objects/notes/{note_id}"
    params = {"properties": "hs_note_body,hs_timestamp"}
    try:
        data = request_json("GET", url, token, params=params)
        return data
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[WARN] Failed to fetch note {note_id}: {exc}", file=sys.stderr)
        return None


def summarize_deals(deals: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        "total_pipeline_usd": 0.0,
        "deal_count": 0,
        "deals_closing_this_week": 0,
    }
    today = date.today()
    for deal in deals:
        amount = deal.get("amount") or 0.0
        summary["total_pipeline_usd"] += amount
        summary["deal_count"] += 1
        days_until_close = deal.get("days_until_close")
        if days_until_close is not None and 0 <= days_until_close <= 7:
            summary["deals_closing_this_week"] += 1
    summary["total_pipeline_usd"] = round(summary["total_pipeline_usd"], 2)
    return summary


def build_by_stage(deals: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "total_usd": 0.0})
    for deal in deals:
        stage = deal.get("stage") or "Unknown"
        entry = result[stage]
        entry["count"] += 1
        entry["total_usd"] += deal.get("amount") or 0.0
    for entry in result.values():
        entry["total_usd"] = round(entry["total_usd"], 2)
    return dict(result)


def build_by_owner(deals: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "total_usd": 0.0, "weighted_usd": 0.0, "deal_ids": []}
    )
    for deal in deals:
        owner = deal.get("owner_name") or "Unassigned"
        entry = result[owner]
        amount = deal.get("amount") or 0.0
        prob = deal.get("stage_probability") or 0.0
        entry["count"] += 1
        entry["total_usd"] += amount
        entry["weighted_usd"] += amount * prob
        entry["deal_ids"].append(deal.get("id"))
    for entry in result.values():
        entry["total_usd"] = round(entry["total_usd"], 2)
        entry["weighted_usd"] = round(entry["weighted_usd"], 2)
    return dict(result)


def trim_text(value: Optional[str], limit: int) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def main() -> None:
    token = load_env_token()

    raw_deals = fetch_all_deals(token)
    owners = fetch_owners(token)

    processed_deals: List[Dict[str, Any]] = []
    today = datetime.now(timezone.utc)

    for raw in raw_deals:
        props = raw.get("properties", {})
        stage = (props.get("dealstage") or "").lower()
        EXCLUDED_STAGES = {"closedwon", "closedlost"} | {
            s.strip().lower() for s in os.environ.get("EXCLUDED_DEAL_STAGES", "").split(",") if s.strip()
        }
        if stage in EXCLUDED_STAGES or "closedwon" in stage or "closedlost" in stage:
            continue

        deal_id = raw.get("id") or ""
        amount = float(props.get("amount") or 0.0)
        close_dt = parse_hs_datetime(props.get("closedate"))
        last_modified = parse_hs_datetime(props.get("hs_lastmodifieddate"))
        created_at = parse_hs_datetime(props.get("createdate"))

        engagements: List[Dict[str, Any]] = []
        last_activity_date: Optional[datetime] = None
        last_activity_type: Optional[str] = None

        engagement_ids = []
        try:
            engagement_ids = fetch_association_ids(token, deal_id, "engagements", 5)
        except SystemExit:
            raise
        except Exception as exc:
            print(f"[WARN] Failed to fetch engagements for deal {deal_id}: {exc}", file=sys.stderr)

        for eng_id in engagement_ids:
            engagement = fetch_engagement(token, eng_id)
            if not engagement:
                continue
            props_e = engagement.get("properties", {})
            timestamp = parse_hs_datetime(props_e.get("hs_timestamp"))
            engagements.append(
                {
                    "type": (props_e.get("hs_engagement_type") or "").upper(),
                    "timestamp": isoformat(timestamp),
                    "preview": trim_text(
                        props_e.get("hs_body_preview")
                        or props_e.get("hs_email_subject")
                        or "",
                        200,
                    ),
                }
            )
        engagements.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        if engagements:
            last_activity_date = parse_hs_datetime(engagements[0]["timestamp"])  # already ISO
            last_activity_type = engagements[0]["type"]

        note_entries: List[Dict[str, Any]] = []
        try:
            note_ids = fetch_association_ids(token, deal_id, "notes", 3)
        except SystemExit:
            raise
        except Exception as exc:
            print(f"[WARN] Failed to fetch notes for deal {deal_id}: {exc}", file=sys.stderr)
            note_ids = []
        for note_id in note_ids:
            note = fetch_note(token, note_id)
            if not note:
                continue
            props_n = note.get("properties", {})
            note_entries.append(
                {
                    "timestamp": isoformat(parse_hs_datetime(props_n.get("hs_timestamp"))),
                    "body": trim_text(props_n.get("hs_note_body"), 300),
                }
            )
        note_entries.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

        owner_id = props.get("hubspot_owner_id")
        owner_info = owners.get(str(owner_id), {}) if owner_id else {}
        owner_name = owner_info.get("name") or props.get("owner_name") or "Unassigned"

        close_date_str = close_dt.date().isoformat() if close_dt else None
        days_until_close: Optional[int] = None
        if close_dt:
            days_until_close = (close_dt.date() - date.today()).days

        if not last_activity_date:
            last_activity_date = last_modified
            last_activity_type = "SYSTEM" if last_activity_date else None

        last_activity_iso = isoformat(last_activity_date)
        days_since_activity: Optional[int] = None
        if last_activity_date:
            days_since_activity = (today - last_activity_date).days

        processed_deals.append(
            {
                "id": deal_id,
                "name": props.get("dealname") or "Untitled Deal",
                "amount": amount,
                "close_date": close_date_str,
                "days_until_close": days_until_close,
                "stage": props.get("dealstage") or "Unknown",
                "stage_probability": float(props.get("hs_deal_stage_probability") or 0.0),
                "owner_id": owner_id,
                "owner_name": owner_name.strip() or "Unassigned",
                "last_modified": isoformat(last_modified),
                "created_at": isoformat(created_at),
                "description": props.get("description") or None,
                "priority": props.get("hs_priority") or None,
                "num_contacts": int(props.get("num_associated_contacts") or 0),
                "days_since_activity": days_since_activity,
                "last_activity_date": last_activity_iso,
                "last_activity_type": last_activity_type,
                "recent_engagements": engagements,
                "recent_notes": note_entries,
                "hubspot_url": f"https://app.hubspot.com/contacts/deals/{deal_id}",
            }
        )

    summary = summarize_deals(processed_deals)
    by_stage = build_by_stage(processed_deals)
    by_owner = build_by_owner(processed_deals)

    output = {
        "generated_at": isoformat(datetime.now(timezone.utc)),
        "week_label": compute_week_label(),
        "summary": summary,
        "owners": owners,
        "deals": processed_deals,
        "by_stage": by_stage,
        "by_owner": by_owner,
    }

    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
