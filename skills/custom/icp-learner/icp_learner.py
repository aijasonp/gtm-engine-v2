#!/usr/bin/env python3
"""ICP Learning Analyzer.

Pulls HubSpot closed-won/lost deals, enriches them with company data, and outputs
win-rate analytics plus an ICP Recommendation Card.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

API_BASE = "https://api.hubapi.com"
DEAL_PROPERTIES = [
    "dealname",
    "amount",
    "dealstage",
    "closedate",
    "hs_closed_lost_reason",
    "pipeline",
]
COMPANY_PROPERTIES = [
    "name",
    "industry",
    "numberofemployees",
    "annualrevenue",
]
EXCLUDED_STAGE = "1099781651"


def chunk_list(items: List[str], size: int = 100) -> List[List[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


class HubSpotClient:
    def __init__(self, token: str, timeout: int = 45) -> None:
        self.token = token.strip()
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, object]] = None,
        body: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        url = API_BASE + path
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            if query:
                url = f"{url}?{query}"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8") if hasattr(exc, "read") else str(exc)
            raise RuntimeError(f"HubSpot HTTP {getattr(exc, 'code', 'error')}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error: {exc}") from exc

    def search_deals(self, limit: int = 100, after: Optional[str] = None) -> Dict[str, object]:
        body: Dict[str, object] = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "dealstage",
                            "operator": "IN",
                            "values": ["closedwon", "closedlost"],
                        }
                    ]
                }
            ],
            "properties": DEAL_PROPERTIES,
            "limit": limit,
        }
        if after:
            body["after"] = after
        return self.request("POST", "/crm/v3/objects/deals/search", body=body)

    def list_associated_companies(self, deal_id: str) -> List[str]:
        params = {"limit": "100"}
        res = self.request(
            "GET",
            f"/crm/v3/objects/deals/{deal_id}/associations/companies",
            params=params,
        )
        results = res.get("results", []) or []
        return [str(item.get("toObjectId")) for item in results if item.get("toObjectId") is not None]

    def get_company(self, company_id: str) -> Dict[str, object]:
        params = {"properties": COMPANY_PROPERTIES}
        return self.request(
            "GET",
            f"/crm/v3/objects/companies/{company_id}",
            params=params,
        )

    def batch_get_deal_company_ids(self, deal_ids: List[str]) -> Dict[str, List[str]]:
        mapping: Dict[str, List[str]] = defaultdict(list)
        if not deal_ids:
            return {}
        for chunk in chunk_list(deal_ids, 100):
            body = {"inputs": [{"id": deal_id} for deal_id in chunk]}
            res = self.request(
                "POST",
                "/crm/v3/associations/deals/companies/batch/read",
                body=body,
            )
            for item in res.get("results", []) or []:
                from_ref = item.get("from") or {}
                deal_id = str(from_ref.get("id")) if from_ref.get("id") is not None else None
                if not deal_id:
                    continue
                for to_item in item.get("to", []) or []:
                    company_id = to_item.get("id")
                    if company_id:
                        mapping[deal_id].append(str(company_id))
        return dict(mapping)

    def batch_get_companies(self, company_ids: List[str]) -> Dict[str, Dict[str, object]]:
        companies: Dict[str, Dict[str, object]] = {}
        if not company_ids:
            return {}
        for chunk in chunk_list(company_ids, 100):
            body = {
                "inputs": [{"id": company_id} for company_id in chunk],
                "properties": COMPANY_PROPERTIES,
            }
            res = self.request(
                "POST",
                "/crm/v3/objects/companies/batch/read",
                body=body,
            )
            for item in res.get("results", []) or []:
                company_id = item.get("id")
                if company_id:
                    companies[str(company_id)] = item
        return companies


def read_env_value(*keys: str) -> Optional[str]:
    for key in keys:
        val = os.environ.get(key)
        if val:
            return val.strip()
    env_path = os.path.expanduser(os.environ.get("GTM_ENV_FILE", "~/.gtm/.env"))
    if not os.path.exists(env_path):
        return None
    with open(env_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            if name in keys:
                return value.strip()
    return None


def load_token() -> str:
    token = read_env_value("HUBSPOT_TOKEN", "HUBSPOT_API_TOKEN", "HUBSPOT_API_KEY")
    if not token:
        raise SystemExit("HUBSPOT_TOKEN is required (env var or GTM_ENV_FILE)")
    return token


def to_float(value: Optional[str]) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def to_int(value: Optional[str]) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def fetch_deals(client: HubSpotClient) -> List[Dict[str, object]]:
    deals: List[Dict[str, object]] = []
    after: Optional[str] = None
    while True:
        response = client.search_deals(after=after)
        deals.extend(response.get("results", []) or [])
        paging = response.get("paging") or {}
        next_page = paging.get("next") or {}
        after = next_page.get("after")
        if not after:
            break
    return deals


def enrich_deals(
    deals: List[Dict[str, object]],
    client: HubSpotClient,
    days: Optional[int],
    *,
    enrich_companies: bool = True,
) -> List[Dict[str, object]]:
    cutoff = None
    if days:
        cutoff = int(time.time() * 1000) - days * 86400 * 1000
    enriched: List[Dict[str, object]] = []
    for deal in deals:
        props = deal.get("properties", {}) or {}
        stage = (props.get("dealstage") or "").lower()
        if stage == EXCLUDED_STAGE:
            continue
        closedate = to_int(props.get("closedate"))
        if cutoff is not None and closedate and closedate < cutoff:
            continue
        status = "won" if stage == "closedwon" else "lost"
        if stage not in {"closedwon", "closedlost"}:
            continue
        amount = to_float(props.get("amount"))
        deal_id = str(deal.get("id"))
        enriched.append(
            {
                "id": deal_id,
                "name": props.get("dealname"),
                "amount": amount,
                "stage": stage,
                "status": status,
                "pipeline": props.get("pipeline"),
                "closedate": closedate,
                "closed_lost_reason": props.get("hs_closed_lost_reason") or "",
                "company": {
                    "id": None,
                    "name": None,
                    "industry": None,
                    "numberofemployees": None,
                    "annualrevenue": None,
                },
            }
        )

    if not enriched or not enrich_companies:
        return enriched

    deal_ids = [record["id"] for record in enriched]
    print("Enriching companies (batch)...", file=sys.stderr)
    deal_company_map = client.batch_get_deal_company_ids(deal_ids)
    company_ids: List[str] = []
    for candidates in deal_company_map.values():
        company_ids.extend(candidates)
    # Preserve order and uniqueness
    seen: Dict[str, None] = {}
    unique_company_ids = []
    for company_id in company_ids:
        if company_id not in seen:
            seen[company_id] = None
            unique_company_ids.append(company_id)
    company_details = client.batch_get_companies(unique_company_ids)

    for record in enriched:
        company_candidates = deal_company_map.get(record["id"], [])
        company_id = company_candidates[0] if company_candidates else None
        properties = ((company_details.get(company_id) or {}).get("properties") or {}) if company_id else {}
        record["company"] = {
            "id": company_id,
            "name": properties.get("name"),
            "industry": properties.get("industry"),
            "numberofemployees": properties.get("numberofemployees"),
            "annualrevenue": properties.get("annualrevenue"),
        }

    return enriched


def bucket_company_size(value: Optional[str]) -> str:
    employees = to_int(value)
    if employees is None:
        return "Unknown"
    if employees <= 100:
        return "1-100"
    if employees <= 500:
        return "101-500"
    if employees <= 2000:
        return "501-2000"
    if employees <= 10000:
        return "2001-10000"
    return "10000+"


def bucket_deal_size(amount: Optional[float]) -> str:
    if amount is None:
        return "Unknown"
    if amount < 50000:
        return "<$50K"
    if amount < 200000:
        return "$50K-$200K"
    if amount < 500000:
        return "$200K-$500K"
    return "$500K+"


def compute_win_rates(records: List[Dict[str, object]], key_func, min_sample: int = 1) -> Dict[str, Dict[str, float]]:
    stats: Dict[str, Dict[str, float]] = {}
    for record in records:
        key = key_func(record)
        stats.setdefault(key, {"wins": 0, "total": 0})
        stats[key]["total"] += 1
        if record["status"] == "won":
            stats[key]["wins"] += 1
    output: Dict[str, Dict[str, float]] = {}
    for key, value in stats.items():
        if value["total"] < min_sample:
            continue
        win_rate = (value["wins"] / value["total"]) * 100 if value["total"] else 0
        output[key] = {
            "wins": value["wins"],
            "total": value["total"],
            "win_rate": round(win_rate, 1),
        }
    return output


def average_amount(records: List[Dict[str, object]], status: str) -> Optional[float]:
    amounts = [r["amount"] for r in records if r["status"] == status and r["amount"]]
    if not amounts:
        return None
    return sum(amounts) / len(amounts)


def summarize_loss_reasons(records: List[Dict[str, object]]) -> List[Tuple[str, int]]:
    reasons = [r["closed_lost_reason"].strip() for r in records if r["status"] == "lost" and r["closed_lost_reason"].strip()]
    counter = Counter(reason for reason in reasons if reason)
    return counter.most_common(5)


def best_categories(win_rates: Dict[str, Dict[str, float]], top_n: int = 3) -> List[str]:
    ranked = sorted(
        win_rates.items(),
        key=lambda item: (item[1]["win_rate"], item[1]["wins"]),
        reverse=True,
    )
    return [f"{name} ({data['win_rate']}% win, {int(data['total'])} deals)" for name, data in ranked[:top_n]]


def build_icp_card(
    industries: Dict[str, Dict[str, float]],
    company_sizes: Dict[str, Dict[str, float]],
    deal_sizes: Dict[str, Dict[str, float]],
    loss_reasons: List[Tuple[str, int]],
    avg_won: Optional[float],
    avg_lost: Optional[float],
    filters: Dict[str, object],
) -> str:
    industry_line = ", ".join(best_categories(industries)) or "Insufficient data"
    size_line = ", ".join(best_categories(company_sizes, top_n=2)) or "Insufficient data"
    deal_line = ", ".join(best_categories(deal_sizes, top_n=2)) or "Insufficient data"
    loss_line = ", ".join(f"{reason} ({count})" for reason, count in loss_reasons) or "No logged reasons"
    avg_line = "N/A"
    if avg_won or avg_lost:
        avg_line = f"Won avg ${avg_won:,.0f} vs Lost avg ${avg_lost:,.0f}" if avg_won and avg_lost else "Partial avg data"

    return "\n".join(
        [
            "## ICP Recommendation Card",
            f"- Date Filter: {filters.get('date_window','All available')}",
            f"- Sweet Spot Industries: {industry_line}",
            f"- Ideal Company Size: {size_line}",
            f"- Ideal Deal Size: {deal_line}",
            f"- Avg Deal Size: {avg_line}",
            f"- Top Loss Reasons: {loss_line}",
            "- Positioning Notes: lead with the pain points that show up most in won deals,"
            "  and map proof points from the product profile to the top industries above.",
        ]
    )


def print_section(title: str) -> None:
    print(f"\n{title}\n" + "-" * len(title))


def human_readable_report(
    records: List[Dict[str, object]],
    industries: Dict[str, Dict[str, float]],
    company_sizes: Dict[str, Dict[str, float]],
    deal_sizes: Dict[str, Dict[str, float]],
    avg_won: Optional[float],
    avg_lost: Optional[float],
    loss_reasons: List[Tuple[str, int]],
) -> None:
    total = len(records)
    wins = len([r for r in records if r["status"] == "won"])
    losses = total - wins
    print_section("ICP Learning Analyzer")
    print(f"Deals analyzed: {total} | Wins: {wins} | Losses: {losses}")

    print_section("Win rate by industry (>=2 deals)")
    if industries:
        for name, data in industries.items():
            print(f"• {name}: {data['win_rate']}% ({int(data['wins'])}/{int(data['total'])})")
    else:
        print("No industries with sufficient volume")

    print_section("Win rate by company size")
    for name, data in company_sizes.items():
        print(f"• {name}: {data['win_rate']}% ({int(data['wins'])}/{int(data['total'])})")

    print_section("Win rate by deal size")
    for name, data in deal_sizes.items():
        print(f"• {name}: {data['win_rate']}% ({int(data['wins'])}/{int(data['total'])})")

    print_section("Average deal size")
    won_text = f"${avg_won:,.0f}" if avg_won else "n/a"
    lost_text = f"${avg_lost:,.0f}" if avg_lost else "n/a"
    print(f"Won: {won_text} | Lost: {lost_text}")

    print_section("Top loss reasons")
    if loss_reasons:
        for reason, count in loss_reasons:
            print(f"• {reason}: {count}")
    else:
        print("No structured loss reasons logged")


def save_json(
    path: str,
    payload: Dict[str, object],
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ICP Learning Analyzer")
    parser.add_argument("--summary", action="store_true", help="Print only the ICP Recommendation Card")
    parser.add_argument("--days", type=int, default=None, help="Limit to deals closed within the last N days")
    parser.add_argument("--no-enrich", action="store_true", help="Skip company enrichment for faster testing")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = load_token()
    client = HubSpotClient(token)
    print("Fetching deals...", file=sys.stderr)
    deals = fetch_deals(client)
    print(f"Fetched {len(deals)} deals.", file=sys.stderr)
    if args.no_enrich:
        print("Skipping company enrichment (--no-enrich).", file=sys.stderr)
    records = enrich_deals(deals, client, args.days, enrich_companies=not args.no_enrich)
    if not records:
        print("No closed deals found for the selected window.")
        return 0

    industries = compute_win_rates(
        records,
        key_func=lambda r: (r["company"].get("industry") or "Unknown"),
        min_sample=2,
    )
    company_sizes = compute_win_rates(
        records,
        key_func=lambda r: bucket_company_size(r["company"].get("numberofemployees")),
    )
    deal_sizes = compute_win_rates(
        records,
        key_func=lambda r: bucket_deal_size(r.get("amount")),
    )
    avg_won = average_amount(records, "won")
    avg_lost = average_amount(records, "lost")
    loss_reasons = summarize_loss_reasons(records)

    filters = {
        "date_window": f"Last {args.days} days" if args.days else "All available",
    }

    icp_card = build_icp_card(
        industries,
        company_sizes,
        deal_sizes,
        loss_reasons,
        avg_won,
        avg_lost,
        filters,
    )

    if not args.summary:
        human_readable_report(records, industries, company_sizes, deal_sizes, avg_won, avg_lost, loss_reasons)
        print_section("ICP Recommendation Card")
    print(icp_card)

    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    output_path = os.path.join(
        os.path.dirname(__file__),
        "outputs",
        f"icp-analysis-{today}.json",
    )
    payload = {
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "filters": filters,
        "counts": {
            "total": len(records),
            "wins": len([r for r in records if r["status"] == "won"]),
            "losses": len([r for r in records if r["status"] == "lost"]),
        },
        "win_rate_by_industry": industries,
        "win_rate_by_company_size": company_sizes,
        "win_rate_by_deal_size": deal_sizes,
        "average_deal_size": {
            "won": avg_won,
            "lost": avg_lost,
        },
        "loss_reasons": loss_reasons,
        "icp_card": icp_card,
    }
    save_json(output_path, payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
