#!/usr/bin/env python3
"""Render a HubSpot account summary from pull_hubspot.py output.

The goal is to give sales/CS teams a fast read on:
- Resolved account metadata (name, domain, industry)
- Deal highlights (closed won vs active pipeline)
- Key contacts derived from deals + activity logs
- Recent engagement snippets (notes, meetings, calls)

Stdlib-only implementation so it can run anywhere Python runs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Render HubSpot account summaries")
    ap.add_argument("--in", dest="inputs", action="append", required=True, help="Input JSON from pull_hubspot.py")
    ap.add_argument("--out", required=True, help="Output text path")
    ap.add_argument("--only", dest="only", action="append", default=[], help="Optional company filters (query or resolved name)")
    ap.add_argument("--max-notes", type=int, default=10)
    ap.add_argument("--max-contacts", type=int, default=8)
    return ap.parse_args()


def load_entries(paths: Sequence[str]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for path in paths:
        data = json.load(open(path))
        entries.extend(data.get("companies", []) or [])
    return entries


def select_entries(entries: List[Dict[str, Any]], filters: Sequence[str]) -> List[Dict[str, Any]]:
    if not filters:
        return entries
    wanted = {f.lower() for f in filters}
    out: List[Dict[str, Any]] = []
    for entry in entries:
        query = (entry.get("query") or "").lower()
        resolved_name = ((entry.get("resolved") or {}).get("properties") or {}).get("name", "").lower()
        if query in wanted or resolved_name in wanted:
            out.append(entry)
    return out


def strip_html(text: Optional[str]) -> str:
    if not text:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    s = re.sub(r"</p\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()


def money(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        amount = float(value)
    except Exception:
        return None
    if abs(amount - round(amount)) < 0.01:
        return f"${int(round(amount)):,}"
    return f"${amount:,.2f}"


def iso_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return None


def summarize_deals(deals: Sequence[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    closed_won: List[str] = []
    active: List[str] = []
    for deal in deals:
        props = deal.get("properties", {}) or {}
        owner = deal.get("owner_label")
        owner_suffix = f" | Owner: {owner}" if owner else ""
        entry = (
            f"{props.get('dealname') or 'Deal ' + str(deal.get('id'))}"
            f" | Stage: {props.get('dealstage') or '—'}"
            f" | Amount: {money(props.get('amount')) or '—'}"
            f" | Close: {iso_date(props.get('closedate')) or '—'}"
            f"{owner_suffix}"
        )
        if str(props.get("hs_is_closed_won")).lower() == "true" or (props.get("dealstage") or "").lower() == "closedwon":
            closed_won.append(entry)
        else:
            active.append(entry)
    return closed_won, active


def contact_key(contact: Dict[str, Any]) -> Tuple[str, str]:
    props = contact.get("properties", {}) or {}
    name = ((props.get("firstname") or "") + " " + (props.get("lastname") or "")).strip()
    title = props.get("jobtitle") or ""
    email = props.get("email") or ""
    return name.strip() or email or str(contact.get("id")), (title + email).lower()


def summarize_contacts(contacts: Sequence[Dict[str, Any]], max_contacts: int) -> List[str]:
    seen = set()
    rows: List[str] = []
    for contact in contacts:
        props = contact.get("properties", {}) or {}
        name = ((props.get("firstname") or "") + " " + (props.get("lastname") or "")).strip() or "(name missing)"
        title = props.get("jobtitle") or "(title missing)"
        email = props.get("email") or "(email missing)"
        owner = contact.get("owner_label")
        owner_suffix = f" — Owner: {owner}" if owner else ""
        key = contact_key(contact)
        if key in seen:
            continue
        seen.add(key)
        rows.append(f"- {name} — {title} ({email}){owner_suffix}")
        if len(rows) >= max_contacts:
            break
    return rows


def gather_engagement_snippets(entry: Dict[str, Any], max_notes: int) -> Dict[str, List[str]]:
    buckets = {"NOTE": [], "MEETING": [], "CALL": [], "EMAIL": []}
    data = entry.get("data", {}) or {}
    engagements = data.get("engagements_v1", {}) or {}
    for deal_id, events in engagements.items():
        for event in events or []:
            info = event.get("engagement") or {}
            etype = info.get("type")
            meta = event.get("metadata") or {}
            ts = int(info.get("timestamp") or 0)
            if etype == "NOTE":
                body = strip_html(meta.get("body"))
                if body:
                    buckets["NOTE"].append((ts, body))
            elif etype == "MEETING":
                title = meta.get("title") or meta.get("body")
                if title:
                    buckets["MEETING"].append((ts, title.strip()))
            elif etype == "CALL":
                title = meta.get("title") or meta.get("body") or meta.get("fromNumber")
                if title:
                    buckets["CALL"].append((ts, strip_html(title)))
            elif etype == "EMAIL":
                subj = meta.get("subject") or meta.get("body")
                if subj:
                    buckets["EMAIL"].append((ts, strip_html(subj)))
    out: Dict[str, List[str]] = {}
    for key, values in buckets.items():
        values.sort(key=lambda tup: tup[0], reverse=True)
        deduped: List[str] = []
        seen = set()
        for _, text in values:
            if text in seen:
                continue
            seen.add(text)
            deduped.append(text if len(text) <= 500 else text[:500].rstrip() + "…")
            if len(deduped) >= max_notes:
                break
        if deduped:
            out[key] = deduped
    return out


def render_entry(entry: Dict[str, Any], max_contacts: int, max_notes: int) -> str:
    if entry.get("error"):
        return f"{entry.get('query')}: ERROR — {entry['error']}\n"

    resolved = entry.get("resolved") or {}
    props = (resolved.get("properties") or {}) if resolved else {}
    header = props.get("name") or entry.get("query") or "(unknown)"
    details = []
    if props.get("domain"):
        details.append(props.get("domain"))
    if props.get("industry"):
        details.append(props.get("industry"))
    if props.get("city") or props.get("country"):
        details.append(
            " / ".join(filter(None, [props.get("city"), props.get("country")]))
        )

    lines = [header]
    if details:
        lines.append("  " + " | ".join(details))

    deals = (entry.get("data", {}) or {}).get("deals", []) or []
    closed_won, active = summarize_deals(deals)
    if closed_won:
        lines.append("  Closed Won deals:")
        lines.extend(f"    {row}" for row in closed_won[:6])
        if len(closed_won) > 6:
            lines.append(f"    (+{len(closed_won) - 6} more)")
    if active:
        lines.append("  Active pipeline:")
        lines.extend(f"    {row}" for row in active[:8])
        if len(active) > 8:
            lines.append(f"    (+{len(active) - 8} more)")

    contacts = (entry.get("data", {}) or {}).get("contacts", []) or []
    contact_rows = summarize_contacts(contacts, max_contacts=max_contacts)
    if contact_rows:
        lines.append("  Key contacts:")
        lines.extend(f"    {row}" for row in contact_rows)

    snippets = gather_engagement_snippets(entry, max_notes=max_notes)
    if snippets:
        lines.append("  Engagement signals:")
        for kind in ("NOTE", "MEETING", "CALL", "EMAIL"):
            entries = snippets.get(kind)
            if not entries:
                continue
            label = {
                "NOTE": "Notes",
                "MEETING": "Meetings",
                "CALL": "Calls",
                "EMAIL": "Emails",
            }[kind]
            lines.append(f"    {label}:")
            for text in entries:
                compact = " ".join(text.strip().split())
                lines.append(f"      - {compact}")

    lines.append("")
    return "\n".join(lines)


def render(entries: Sequence[Dict[str, Any]], *, max_contacts: int, max_notes: int) -> str:
    header = [
        "HubSpot account summary",
        "Generated: " + dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "",
        "Data source: scripts/pull_hubspot.py",
        "",
    ]
    body = [render_entry(entry, max_contacts=max_contacts, max_notes=max_notes) for entry in entries]
    return "\n".join(header + body)


def main() -> int:
    args = parse_args()
    entries = load_entries(args.inputs)
    selected = select_entries(entries, args.only)
    if not selected:
        raise SystemExit("No matching entries to render")
    output = render(selected, max_contacts=args.max_contacts, max_notes=args.max_notes)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
