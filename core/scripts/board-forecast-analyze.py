#!/usr/bin/env python3
"""Analyze board forecast data and produce bucket rows for sheet building."""
import os
import json, sys
from datetime import date, datetime

OUT = os.path.expanduser("~/.openclaw/workspace/output")
d = json.load(open(f"{OUT}/board-forecast-2026-09-23.json"))
deals = d["deals"]
owners = d["owners"]
deal_companies = d["deal_companies"]
comp_names = d["company_names"]

# Stage metadata
pipe = json.load(open(f"{OUT}/pipelines.json"))
stage_label = {}
stage_prob = {}
stage_closed = {}
for p in pipe["results"]:
    for s in p["stages"]:
        stage_label[s["id"]] = s["label"]
        stage_prob[s["id"]] = float(s["metadata"].get("probability", 0))
        stage_closed[s["id"]] = s["metadata"].get("isClosed") == "true"

CLOSED_WON = "closedwon"
CLOSED_LOST = "closedlost"

def dealtype_map(v):
    if not v:
        return None
    v = v.strip().lower()
    if v in ("newbusiness", "new_business", "new business"):
        return "New Business"
    if v in ("upsell",):
        return "Upsell"
    return None  # excluded

def owner_name(oid):
    if not oid:
        return ""
    return owners.get(str(oid), "")

def company_name(did):
    ids = deal_companies.get(did, [])
    names = [comp_names.get(i, "") for i in ids if comp_names.get(i)]
    return ", ".join(names) if names else ""

def parse_date(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
    except Exception:
        return None

def amount(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0

Q3_START = date(2026, 7, 1)
Q3_END = date(2026, 9, 30)
Q4_START = date(2026, 10, 1)
Q4_END = date(2026, 12, 31)

# Filter: new business + upsell only
included = []
excluded = []
for deal in deals:
    dt = dealtype_map(deal["properties"].get("dealtype"))
    if dt:
        included.append((deal, dt))
    else:
        excluded.append(deal)

print(f"Included (new business + upsell): {len(included)}")
print(f"Excluded: {len(excluded)}")

# Build enriched records
recs = []
for deal, dt in included:
    p = deal["properties"]
    recs.append({
        "id": deal["id"],
        "name": p.get("dealname", ""),
        "company": company_name(deal["id"]),
        "amount": amount(p.get("amount")),
        "stage": p.get("dealstage"),
        "stage_label": stage_label.get(p.get("dealstage"), p.get("dealstage")),
        "stage_prob": stage_prob.get(p.get("dealstage"), 0),
        "pipeline": p.get("pipeline"),
        "closedate": parse_date(p.get("closedate")),
        "owner": owner_name(p.get("hubspot_owner_id")),
        "dealtype": dt,
        "fc": p.get("hs_forecast_category"),
        "next_step": p.get("hs_next_step") or "",
        "lastmod": p.get("hs_lastmodifieddate", "")[:10],
        "is_closed_won": p.get("dealstage") == CLOSED_WON,
        "is_closed_lost": p.get("dealstage") == CLOSED_LOST,
    })

# Buckets
q3_won = [r for r in recs if r["is_closed_won"] and r["closedate"] and Q3_START <= r["closedate"] <= Q3_END]
q3_open = [r for r in recs if not r["is_closed_won"] and not r["is_closed_lost"] and r["closedate"] and r["closedate"] <= Q3_END]
q4_pipe = [r for r in recs if not r["is_closed_won"] and not r["is_closed_lost"] and r["closedate"] and Q4_START <= r["closedate"] <= Q4_END]

print(f"Q3 won: {len(q3_won)}  total={sum(r['amount'] for r in q3_won):,.0f}")
print(f"Q3 open: {len(q3_open)}  total={sum(r['amount'] for r in q3_open):,.0f}")
print(f"Q4 pipe: {len(q4_pipe)}  total={sum(r['amount'] for r in q4_pipe):,.0f}")

# Data quality flags
no_amount = [r for r in recs if r["amount"] == 0]
no_owner = [r for r in recs if not r["owner"]]
no_fc = [r for r in recs if not r["fc"]]
print(f"Missing amount: {len(no_amount)}")
print(f"Missing owner: {len(no_owner)}")
print(f"Missing forecast category: {len(no_fc)}")

# Save analysis
json.dump({
    "q3_won": q3_won, "q3_open": q3_open, "q4_pipe": q4_pipe,
    "excluded_count": len(excluded),
    "dealtype_map_used": {"newbusiness": "New Business", "Upsell": "Upsell",
                          "Renewal": "EXCLUDED", "Services": "EXCLUDED", None: "EXCLUDED"},
}, open(f"{OUT}/board-forecast-analysis.json", "w"), indent=2, default=str)
print("Saved analysis.")
