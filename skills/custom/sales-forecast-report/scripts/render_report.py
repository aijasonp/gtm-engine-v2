#!/usr/bin/env python3
"""Render the weekly sales forecast HTML report for Google Docs ingestion.

Branding is set by env: REPORT_COMPANY (title prefix), REPORT_LOGO (path to a PNG),
REPORT_ACCENT (hex accent color).
"""
import argparse
import os
import base64
import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

STAGE_ORDER = [
    "Appointment Scheduled",
    "Qualified to Buy",
    "Presentation Scheduled",
    "Decision Maker Bought-In",
    "Contract Sent",
    "Closed Won",
    "Closed Lost",
]
INK = "#111827"
ACCENT = os.environ.get("REPORT_ACCENT", "#1F4E79")
LIGHT_GRAY = "#F7F8F8"
SILVER = "#9CA3AF"
COMPANY = os.environ.get("REPORT_COMPANY", "").strip()
REPORT_TITLE = (COMPANY + " " if COMPANY else "") + "Weekly Sales Forecast"
SUCCESS = "#22C55E"
WARNING = "#F59E0B"
DANGER = "#EF4444"


def fmt_usd(amount: Any) -> str:
    try:
        value = float(amount or 0.0)
    except (TypeError, ValueError):
        value = 0.0
    abs_value = abs(value)
    if abs_value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs_value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"


def fmt_date(iso_string: Any) -> str:
    if not iso_string:
        return "-"
    text = str(iso_string)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return str(iso_string)
    return dt.strftime("%b %d")


def confidence_color(score: float) -> str:
    if score >= 70:
        return SUCCESS
    if score >= 40:
        return WARNING
    return DANGER


def flag_severity(flag: str) -> str:
    critical_tokens = [
        "NO_CLOSE",
        "NO_OWNER",
        "CRITICAL",
        "IMMEDIATE",
        "BLOCKED",
        "OVERDUE",
        "STALE",
        "PAST_DUE",
    ]
    flag_upper = flag.upper()
    if any(token in flag_upper for token in critical_tokens):
        return "critical"
    return "warning"


def load_logo_data() -> str:
    logo_env = os.environ.get("REPORT_LOGO", "")
    logo_path = Path(os.path.expanduser(logo_env)) if logo_env else None
    if logo_path and logo_path.exists():
        encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
        return (
            "<img src=\"data:image/png;base64," + encoded +
            "\" alt=\"Company logo\" style=\"width:180px;vertical-align:middle;\"/>"
        )
    return f"<p style=\"font-weight:bold;font-size:18px;\">{escape(COMPANY)}</p>" if COMPANY else ""


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def ensure_defaults(analysis: Dict[str, Any], deal_id: str) -> Dict[str, Any]:
    defaults = {
        "confidence": 50,
        "confidence_label": "Needs Review",
        "next_steps": "Pending analysis",
        "weekly_action": "Review status",
        "hygiene_flags": [],
        "priority": "maintain",
    }
    deal_info = analysis.get("deals", {}).get(deal_id, {})
    merged = defaults.copy()
    merged.update({k: v for k, v in deal_info.items() if v is not None})
    return merged


def build_stage_rows(stage_stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for stage in STAGE_ORDER:
        if stage not in stage_stats:
            continue
        stats = stage_stats[stage]
        count = stats.get("count", 0)
        total = stats.get("total_usd", 0.0)
        avg = total / count if count else 0.0
        rows.append({"stage": stage, "count": count, "total": total, "avg": avg})
    return rows


def build_by_owner(deals: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for deal in deals:
        owner = deal.get("owner_name") or "Unassigned"
        grouped.setdefault(owner, []).append(deal)
    return grouped


def safe_days_until_close(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def sort_deals(priority: str, confidence: float) -> Tuple[int, float]:
    priority_rank = {"immediate": 0, "important": 1, "maintain": 2}
    return (priority_rank.get(priority, 3), -confidence)


def render_flags(flags: List[str]) -> str:
    if not flags:
        return (
            f"<span style=\"display:inline-block;padding:2px 8px;"
            f"background-color:{SUCCESS};color:#FFFFFF;font-size:12px;"
            f"border-radius:12px;\">Clean</span>"
        )
    badges = []
    for flag in flags:
        severity = flag_severity(flag)
        background = DANGER if severity == "critical" else WARNING
        text_color = "#FFFFFF" if severity == "critical" else INK
        badges.append(
            "<span style=\"display:inline-block;padding:2px 8px;"
            f"margin-right:4px;margin-bottom:4px;border-radius:12px;"
            f"background-color:{background};color:{text_color};font-size:12px;\">"
            f"{escape(flag)}</span>"
        )
    return "".join(badges)


def render_weekly_priorities(items: List[Dict[str, Any]]) -> str:
    buckets = {"immediate": [], "important": [], "maintain": []}
    for item in items:
        priority = (item.get("priority") or "maintain").lower()
        buckets.setdefault(priority, []).append(item)
    sections = []
    order = [
        ("immediate", "Immediate Action"),
        ("important", "Important"),
        ("maintain", "Maintain"),
    ]
    for key, title in order:
        entries = buckets.get(key, [])
        if entries:
            lines = []
            for entry in entries:
                deal_name = entry.get("deal_name") or entry.get("deal") or "Deal"
                action = entry.get("action") or "Pending next steps"
                lines.append(
                    f"<p style=\"margin:4px 0;\"><strong>{escape(deal_name)}</strong>: {escape(action)}</p>"
                )
            body = "".join(lines)
        else:
            body = "<p style=\"margin:4px 0;color:#666666;\">No priorities listed</p>"
        sections.append(
            f"<h3 style=\"color:{ACCENT};margin:16px 0 4px;\">{title}</h3>{body}"
        )
    return "".join(sections)


def hygiene_text_color(score: float) -> str:
    return confidence_color(score)


def build_html(data: Dict[str, Any], analysis: Dict[str, Any], output_path: Path) -> str:
    deals = data.get("deals", [])
    stage_stats = data.get("by_stage", {})
    owner_stats = data.get("by_owner", {})
    summary = data.get("summary", {})
    week_label = data.get("week_label", "Current Week")
    generated_at = (
        data.get("generated_at")
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )

    total_pipeline = summary.get("total_pipeline_usd") or sum(
        (deal.get("amount") or 0.0) for deal in deals
    )
    weighted_forecast = sum(
        (deal.get("amount") or 0.0) * (deal.get("stage_probability") or 0.0)
        for deal in deals
    )
    closing_deals = []
    for deal in deals:
        days_int = safe_days_until_close(deal.get("days_until_close"))
        if days_int is not None and 0 <= days_int <= 7:
            closing_deals.append(deal)
    hygiene_score = float(analysis.get("hygiene_score", 100.0))

    stage_rows = build_stage_rows(stage_stats)

    hygiene_rows = []
    for deal in deals:
        merged = ensure_defaults(analysis, deal.get("id"))
        flags = merged.get("hygiene_flags") or []
        if not flags:
            continue
        hygiene_rows.append(
            {
                "name": deal.get("name") or "Deal",
                "owner": deal.get("owner_name") or "Unassigned",
                "amount": deal.get("amount"),
                "flags": flags,
                "activity": deal.get("days_since_activity"),
            }
        )

    owner_groups = build_by_owner(deals)
    # Reps alphabetically, Unassigned last
    rep_priority = sorted(r for r in owner_groups if r != "Unassigned") + ["Unassigned"]
    all_reps = list(owner_groups.keys())
    for rep in rep_priority:
        if rep not in all_reps:
            all_reps.append(rep)
    ordered_reps: List[str] = []
    seen = set()
    for name in rep_priority + sorted(set(all_reps) - set(rep_priority)):
        if name not in seen:
            ordered_reps.append(name)
            seen.add(name)

    analysis_rows = []
    for rep_name, rep_deals in owner_groups.items():
        annotated: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        for deal in rep_deals:
            merged = ensure_defaults(analysis, deal.get("id"))
            annotated.append((deal, merged))
        for deal, merged in sorted(
            annotated,
            key=lambda item: sort_deals(
                (item[1].get("priority") or "maintain").lower(),
                float(item[1].get("confidence", 50)),
            ),
        ):
            analysis_rows.append({"rep": rep_name, "deal": deal, "analysis": merged})

    weekly_priorities_html = render_weekly_priorities(
        analysis.get("weekly_priorities", [])
    )

    logo_html = load_logo_data()
    hygiene_color = hygiene_text_color(hygiene_score)

    html_parts = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "<meta charset=\"utf-8\" />",
        f"<title>{escape(REPORT_TITLE)}</title>",
        "</head>",
        f"<body style=\"font-family:Helvetica,Arial,sans-serif;color:{INK};margin:24px;\">",
    ]

    # Section 1: Header
    html_parts.append(
        f"<table style=\"width:100%;border-collapse:collapse;\"><tr>"
        f"<td style=\"vertical-align:top;\">{logo_html}</td>"
        f"<td style=\"text-align:right;vertical-align:top;\">"
        f"<p style=\"margin:0;color:{ACCENT};font-size:18px;font-weight:bold;\">{escape(REPORT_TITLE)}</p>"
        f"<p style=\"margin:4px 0 0 0;color:{INK};font-size:14px;\">Week of {escape(week_label)}</p>"
        f"<p style=\"margin:4px 0 0 0;color:{SILVER};font-size:12px;\">Generated {escape(generated_at)}</p>"
        f"<p style=\"margin:8px 0 0 0;color:{ACCENT};font-size:28px;font-weight:bold;\">Pipeline {fmt_usd(total_pipeline)}</p>"
        "</td></tr></table>"
    )
    html_parts.append(
        f"<hr style=\"border:0;border-top:2px solid {ACCENT};margin:12px 0 24px;\"/>"
    )

    # Section 2: Executive Summary
    html_parts.append(
        f"<h2 style=\"color:{ACCENT};margin:24px 0 8px;\">Executive Summary</h2>"
    )
    metrics = [
        ("Total Pipeline", fmt_usd(total_pipeline), INK),
        ("Weighted Forecast", fmt_usd(weighted_forecast), INK),
        ("Deals Closing This Week", str(len(closing_deals)), INK),
        ("Hygiene Score", f"{hygiene_score:.0f}%", hygiene_color),
    ]
    summary_cells = []
    for label, value, color in metrics:
        summary_cells.append(
            f"<td style=\"padding:12px;background-color:{LIGHT_GRAY};"
            f"border:1px solid {SILVER};text-align:left;\">"
            f"<p style=\"margin:0;font-size:12px;font-weight:bold;color:{INK};\">{label}</p>"
            f"<p style=\"margin:6px 0 0 0;font-size:20px;font-weight:bold;color:{color};\">{value}</p>"
            "</td>"
        )
    html_parts.append(
        "<table style=\"width:100%;border-collapse:collapse;\"><tr>"
        + "".join(summary_cells)
        + "</tr></table>"
    )

    # Section 3: Pipeline by Stage
    html_parts.append(
        f"<h2 style=\"color:{ACCENT};margin:24px 0 8px;\">Pipeline by Stage</h2>"
    )
    html_parts.append(
        f"<table style=\"width:100%;border-collapse:collapse;border:1px solid {SILVER};\">"
        f"<tr style=\"background-color:{ACCENT};color:#FFFFFF;\">"
        "<th style=\"padding:8px;text-align:left;\">Stage Name</th>"
        "<th style=\"padding:8px;text-align:left;\">Deal Count</th>"
        "<th style=\"padding:8px;text-align:left;\">Total Value</th>"
        "<th style=\"padding:8px;text-align:left;\">Avg Deal Size</th>"
        "</tr>"
    )
    if stage_rows:
        for idx, row in enumerate(stage_rows):
            background = LIGHT_GRAY if idx % 2 else "#FFFFFF"
            html_parts.append(
                f"<tr style=\"background-color:{background};\">"
                f"<td style=\"padding:8px;\">{escape(row['stage'])}</td>"
                f"<td style=\"padding:8px;\">{row['count']}</td>"
                f"<td style=\"padding:8px;\">{fmt_usd(row['total'])}</td>"
                f"<td style=\"padding:8px;\">{fmt_usd(row['avg'])}</td>"
                "</tr>"
            )
    else:
        html_parts.append(
            f"<tr><td colspan=\"4\" style=\"padding:8px;color:{SILVER};\">No stage data</td></tr>"
        )
    html_parts.append("</table>")

    # Section 4: Forecast Hygiene
    if hygiene_rows:
        html_parts.append(
            f"<h2 style=\"color:{ACCENT};margin:24px 0 8px;\">Forecast Hygiene</h2>"
        )
        html_parts.append(
            f"<p style=\"margin:4px 0;color:{hygiene_color};font-weight:bold;\">{hygiene_score:.0f}% of deals are clean</p>"
        )
        html_parts.append(
            f"<table style=\"width:100%;border-collapse:collapse;border:1px solid {SILVER};\">"
            f"<tr style=\"background-color:{ACCENT};color:#FFFFFF;\">"
            "<th style=\"padding:8px;text-align:left;\">Deal Name</th>"
            "<th style=\"padding:8px;text-align:left;\">Rep</th>"
            "<th style=\"padding:8px;text-align:left;\">Amount</th>"
            "<th style=\"padding:8px;text-align:left;\">Flags</th>"
            "<th style=\"padding:8px;text-align:left;\">Days Since Activity</th>"
            "</tr>"
        )
        for idx, row in enumerate(hygiene_rows):
            background = LIGHT_GRAY if idx % 2 else "#FFFFFF"
            html_parts.append(
                f"<tr style=\"background-color:{background};\">"
                f"<td style=\"padding:8px;\">{escape(row['name'])}</td>"
                f"<td style=\"padding:8px;\">{escape(row['owner'])}</td>"
                f"<td style=\"padding:8px;\">{fmt_usd(row['amount'])}</td>"
                f"<td style=\"padding:8px;\">{render_flags(row['flags'])}</td>"
                f"<td style=\"padding:8px;\">{row['activity'] if row['activity'] is not None else '-'}</td>"
                "</tr>"
            )
        html_parts.append("</table>")

    # Section 5: Rep Scorecards
    html_parts.append(
        f"<h2 style=\"color:{ACCENT};margin:24px 0 8px;\">Rep Scorecards</h2>"
    )
    for rep_name in ordered_reps:
        rep_stats = owner_stats.get(rep_name, {})
        rep_deals = owner_groups.get(rep_name, [])
        pipeline_total = rep_stats.get("total_usd")
        if pipeline_total is None:
            pipeline_total = sum((deal.get("amount") or 0.0) for deal in rep_deals)
        deal_count = rep_stats.get("count") or len(rep_deals)
        weighted_total = rep_stats.get("weighted_usd")
        if weighted_total is None:
            weighted_total = sum(
                (deal.get("amount") or 0.0) * (deal.get("stage_probability") or 0.0)
                for deal in rep_deals
            )
        closing_count = 0
        for deal in rep_deals:
            days_int = safe_days_until_close(deal.get("days_until_close"))
            if days_int is not None and 0 <= days_int <= 7:
                closing_count += 1
        html_parts.append(
            f"<h3 style=\"color:{ACCENT};margin:12px 0 4px;\">{escape(rep_name)}</h3>"
        )
        html_parts.append(
            f"<table style=\"width:100%;border-collapse:collapse;margin-bottom:12px;\">"
            f"<tr style=\"background-color:{ACCENT};color:#FFFFFF;\">"
            "<th style=\"padding:6px;text-align:left;\">Pipeline $</th>"
            "<th style=\"padding:6px;text-align:left;\">Deal Count</th>"
            "<th style=\"padding:6px;text-align:left;\">Weighted Forecast</th>"
            "<th style=\"padding:6px;text-align:left;\">Deals Closing This Week</th>"
            "</tr>"
            f"<tr style=\"background-color:{LIGHT_GRAY};\">"
            f"<td style=\"padding:6px;\">{fmt_usd(pipeline_total)}</td>"
            f"<td style=\"padding:6px;\">{deal_count}</td>"
            f"<td style=\"padding:6px;\">{fmt_usd(weighted_total)}</td>"
            f"<td style=\"padding:6px;\">{closing_count}</td>"
            "</tr></table>"
        )

    # Section 6: Deal Analysis
    html_parts.append(
        f"<h2 style=\"color:{ACCENT};margin:24px 0 8px;\">Deal Analysis</h2>"
    )
    html_parts.append(
        f"<table style=\"width:100%;border-collapse:collapse;border:1px solid {SILVER};\">"
        f"<tr style=\"background-color:{ACCENT};color:#FFFFFF;\">"
        "<th style=\"padding:8px;text-align:left;\">Deal Name</th>"
        "<th style=\"padding:8px;text-align:left;\">Rep</th>"
        "<th style=\"padding:8px;text-align:left;\">Amount</th>"
        "<th style=\"padding:8px;text-align:left;\">Close Date</th>"
        "<th style=\"padding:8px;text-align:left;\">Stage</th>"
        "<th style=\"padding:8px;text-align:left;\">Confidence</th>"
        "<th style=\"padding:8px;text-align:left;\">Next Steps</th>"
        "<th style=\"padding:8px;text-align:left;\">What Must Happen This Week</th>"
        "<th style=\"padding:8px;text-align:left;\">Flags</th>"
        "</tr>"
    )
    if analysis_rows:
        for idx, row in enumerate(analysis_rows):
            deal = row["deal"]
            details = row["analysis"]
            confidence = float(details.get("confidence", 50))
            confidence_bg = confidence_color(confidence)
            background = LIGHT_GRAY if idx % 2 else "#FFFFFF"
            hubspot_url = deal.get("hubspot_url") or "#"
            html_parts.append(
                f"<tr style=\"background-color:{background};\">"
                f"<td style=\"padding:8px;\"><a href=\"{escape(hubspot_url)}\" style=\"color:{ACCENT};font-weight:bold;\">{escape(deal.get('name', 'Deal'))}</a></td>"
                f"<td style=\"padding:8px;\">{escape(row['rep'])}</td>"
                f"<td style=\"padding:8px;\">{fmt_usd(deal.get('amount'))}</td>"
                f"<td style=\"padding:8px;\">{fmt_date(deal.get('close_date'))}</td>"
                f"<td style=\"padding:8px;\">{escape(deal.get('stage', '-'))}</td>"
                f"<td style=\"padding:8px;\"><span style=\"display:inline-block;padding:4px 10px;border-radius:12px;color:#FFFFFF;background-color:{confidence_bg};\">{confidence:.0f}% {escape(details.get('confidence_label', ''))}</span></td>"
                f"<td style=\"padding:8px;\">{escape(details.get('next_steps', 'Pending analysis'))}</td>"
                f"<td style=\"padding:8px;\">{escape(details.get('weekly_action', 'Review status'))}</td>"
                f"<td style=\"padding:8px;\">{render_flags(details.get('hygiene_flags') or [])}</td>"
                "</tr>"
            )
    else:
        html_parts.append(
            f"<tr><td colspan=\"9\" style=\"padding:8px;color:{SILVER};\">No deal analysis available</td></tr>"
        )
    html_parts.append("</table>")

    # Section 7: Weekly Priorities
    html_parts.append(
        f"<h2 style=\"color:{ACCENT};margin:24px 0 8px;\">Weekly Priorities</h2>"
    )
    html_parts.append(weekly_priorities_html)

    # Section 8: Footer
    html_parts.append(
        f"<hr style=\"border:0;border-top:1px solid {SILVER};margin:32px 0 12px;\"/>"
    )
    today = datetime.now().strftime("%b %d, %Y")
    html_parts.append(
        f"<p style=\"color:{SILVER};font-size:12px;\">Generated by the GTM forecast agent • {today}</p>"
    )

    html_parts.append("</body></html>")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_content = "".join(html_parts)
    output_path.write_text(html_content, encoding="utf-8")
    return html_content


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the sales forecast report")
    parser.add_argument("--data", required=True, help="Path to JSON data from pull_deals")
    parser.add_argument("--analysis", required=True, help="Path to analysis JSON")
    parser.add_argument("--output", required=True, help="Output HTML path")
    args = parser.parse_args()

    data_path = Path(args.data)
    analysis_path = Path(args.analysis)
    output_path = Path(args.output)

    data = load_json(data_path)
    analysis = load_json(analysis_path) if analysis_path.exists() else {"deals": {}}

    build_html(data, analysis, output_path)


if __name__ == "__main__":
    main()
