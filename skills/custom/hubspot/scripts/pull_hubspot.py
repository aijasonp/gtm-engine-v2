#!/usr/bin/env python3
"""Pull HubSpot CRM data for one or more company queries.

Features:
- Search and resolve HubSpot companies from a free-text query
- Aggregate associated deals, contacts, and related companies
- Fetch full engagement history for each deal using the legacy v1 Engagements API
- Surface pipeline + stage metadata for downstream summarizers
- Stdlib-only (urllib) implementation with retry handling for rate limits

Usage:
    export HUBSPOT_API_TOKEN=pat-...
    python scripts/pull_hubspot.py --out /tmp/hubspot.json "Acme Inc"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Tuple

from hubspot_owners import OwnerResolver

API_BASE = "https://api.hubapi.com"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class HubSpotClient:
    def __init__(self, token: str, *, timeout: int = 45) -> None:
        self.token = token
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        max_attempts: int = 6,
    ) -> Dict[str, Any]:
        from urllib.parse import urlencode

        url = API_BASE + path
        if params:
            query = urlencode({k: v for k, v in params.items() if v is not None})
            if query:
                url += f"?{query}"

        data = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")

        for attempt in range(max_attempts):
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                payload = e.read().decode("utf-8") if hasattr(e, "read") else ""
                status = getattr(e, "code", None)
                if status in RETRYABLE_STATUS and attempt < max_attempts - 1:
                    delay = min(2 ** attempt, 20)
                    time.sleep(delay)
                    continue
                raise RuntimeError(f"HubSpot error {status} on {method} {path}: {payload}")
            except urllib.error.URLError as e:
                if attempt == max_attempts - 1:
                    raise RuntimeError(f"Network error on {method} {path}: {e}")
                time.sleep(min(2 ** attempt, 10))
        raise RuntimeError(f"HubSpot request failed after {max_attempts} attempts: {method} {path}")

    # --- High-level helpers -------------------------------------------------

    def search_companies(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        body = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "name",
                            "operator": "CONTAINS_TOKEN",
                            "value": query,
                        }
                    ]
                }
            ],
            "properties": [
                "name",
                "domain",
                "industry",
                "city",
                "country",
                "description",
                "hs_lastmodifieddate",
            ],
            "limit": limit,
        }
        res = self.request("POST", "/crm/v3/objects/companies/search", body=body)
        return res.get("results", [])

    def search_deals(self, query: str, *, properties: List[str]) -> List[Dict[str, Any]]:
        body = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "dealname",
                            "operator": "CONTAINS_TOKEN",
                            "value": query,
                        }
                    ]
                }
            ],
            "properties": properties,
            "limit": 50,
        }
        res = self.request("POST", "/crm/v3/objects/deals/search", body=body)
        return res.get("results", [])

    def list_associations(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        *,
        page_limit: int = 100,
    ) -> List[str]:
        out: List[str] = []
        after: Optional[str] = None
        while True:
            params = {"limit": str(page_limit)}
            if after:
                params["after"] = after
            res = self.request(
                "GET",
                f"/crm/v3/objects/{from_type}/{from_id}/associations/{to_type}",
                params=params,
            )
            results = res.get("results", []) or []
            out.extend(str(r.get("toObjectId")) for r in results if r.get("toObjectId") is not None)
            next_page = (res.get("paging") or {}).get("next")
            if not next_page:
                break
            after = str(next_page.get("after"))
        return _dedupe(out)

    def batch_read(self, obj_type: str, ids: Iterable[str], properties: List[str]) -> List[Dict[str, Any]]:
        ids_list = [str(i) for i in ids if i]
        if not ids_list:
            return []
        chunk = 100
        out: List[Dict[str, Any]] = []
        for i in range(0, len(ids_list), chunk):
            inputs = [{"id": _id} for _id in ids_list[i : i + chunk]]
            body = {"inputs": inputs, "properties": properties}
            res = self.request("POST", f"/crm/v3/objects/{obj_type}/batch/read", body=body)
            out.extend(res.get("results", []) or [])
        return out

    def list_engagements_v1(self, deal_id: str, limit_total: int = 800) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        offset: Optional[int] = None
        while True:
            params = {"limit": "100"}
            if offset is not None:
                params["offset"] = str(offset)
            res = self.request(
                "GET",
                f"/engagements/v1/engagements/associated/deal/{deal_id}/paged",
                params=params,
            )
            out.extend(res.get("results", []) or [])
            if len(out) >= limit_total or not res.get("hasMore"):
                return out[:limit_total]
            offset = res.get("offset")

    def pipelines(self) -> Dict[str, Any]:
        return self.request("GET", "/crm/v3/pipelines/deals")


# --- Utility helpers --------------------------------------------------------

def _dedupe(seq: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in seq:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def choose_company(candidates: List[Dict[str, Any]], query: str) -> Optional[Dict[str, Any]]:
    q = (query or "").strip().lower()
    if not candidates:
        return None

    def score(entry: Dict[str, Any]) -> Tuple[int, int]:
        props = entry.get("properties", {}) or {}
        name = (props.get("name") or "").strip().lower()
        domain = (props.get("domain") or "").strip().lower()
        exact = 1 if name == q else 0
        starts = 1 if name.startswith(q) else 0
        contains = 1 if q and q in name else 0
        domain_hit = 1 if q and (q == domain or q in domain) else 0
        return (exact * 100 + starts * 10 + contains * 5 + domain_hit * 20, len(name) or 999)

    ranked = sorted(candidates, key=lambda e: (-score(e)[0], score(e)[1]))
    return ranked[0]


# --- Main data gathering ----------------------------------------------------

def collect_company_payload(client: HubSpotClient, query: str) -> Dict[str, Any]:
    deal_props = [
        "dealname",
        "amount",
        "pipeline",
        "dealstage",
        "closedate",
        "createdate",
        "hs_is_closed",
        "hs_is_closed_won",
        "hs_lastmodifieddate",
        "description",
        "next_step",
        "hubspot_owner_id",
    ]
    contact_props = [
        "firstname",
        "lastname",
        "email",
        "phone",
        "jobtitle",
        "company",
        "hs_lastmodifieddate",
        "hubspot_owner_id",
    ]
    company_props = [
        "name",
        "domain",
        "industry",
        "description",
        "city",
        "country",
        "numberofemployees",
        "createdate",
        "hs_lastmodifieddate",
    ]

    candidates = client.search_companies(query)
    resolved = choose_company(candidates, query)
    company_id = str(resolved.get("id")) if resolved else None

    # Resolve owner IDs -> names/emails for contacts + deals below.
    owner_resolver = OwnerResolver(client.token)
    owner_map = owner_resolver.owners()

    # Store top candidates for debugging/review
    candidate_view = []
    for entry in candidates[:5]:
        props = entry.get("properties", {}) or {}
        candidate_view.append(
            {
                "id": entry.get("id"),
                "name": props.get("name"),
                "domain": props.get("domain"),
                "industry": props.get("industry"),
            }
        )

    deal_ids: List[str] = []
    if company_id:
        try:
            deal_ids.extend(client.list_associations("companies", company_id, "deals"))
        except Exception as exc:
            candidate_view.append({"error_associations": str(exc)})

    # deals found via text search as a fallback
    deal_search_hits = client.search_deals(query, properties=deal_props)
    deal_ids.extend(str(d.get("id")) for d in deal_search_hits if d.get("id"))
    deal_ids = _dedupe(deal_ids)

    deals = client.batch_read("deals", deal_ids, properties=deal_props)
    for deal in deals:
        owner_id = (deal.get("properties") or {}).get("hubspot_owner_id")
        if owner_id:
            deal.setdefault("owner_label", owner_resolver.label(owner_id))

    contact_ids: List[str] = []
    if company_id:
        try:
            contact_ids.extend(client.list_associations("companies", company_id, "contacts"))
        except Exception as exc:
            candidate_view.append({"error_contacts": str(exc)})

    engagements_v1: Dict[str, List[Dict[str, Any]]] = {}
    engagement_contact_ids: List[str] = []
    engagement_company_ids: List[str] = []

    for deal_id in deal_ids:
        try:
            history = client.list_engagements_v1(deal_id)
        except Exception as exc:
            history = [{"error": str(exc)}]
        engagements_v1[deal_id] = history
        for record in history:
            assoc = record.get("associations") or {}
            engagement_contact_ids.extend(str(cid) for cid in assoc.get("contactIds") or [])
            engagement_company_ids.extend(str(cid) for cid in assoc.get("companyIds") or [])

    # gather contacts linked via deals + engagements
    for deal_id in deal_ids:
        try:
            contact_ids.extend(client.list_associations("deals", deal_id, "contacts"))
        except Exception:
            continue

    contact_ids.extend(engagement_contact_ids)
    contacts = client.batch_read("contacts", _dedupe(contact_ids), properties=contact_props)
    for contact in contacts:
        owner_id = (contact.get("properties") or {}).get("hubspot_owner_id")
        if owner_id:
            contact.setdefault("owner_label", owner_resolver.label(owner_id))

    company_ids = []
    if company_id:
        company_ids.append(company_id)
    company_ids.extend(engagement_company_ids)
    companies = client.batch_read("companies", _dedupe(company_ids), properties=company_props)

    return {
        "query": query,
        "resolved": resolved,
        "candidates": candidate_view,
        "data": {
            "deal_ids": deal_ids,
            "deals": deals,
            "deal_search_preview": [
                {
                    "id": d.get("id"),
                    "dealname": (d.get("properties") or {}).get("dealname"),
                    "pipeline": (d.get("properties") or {}).get("pipeline"),
                }
                for d in deal_search_hits[:8]
            ],
            "contacts": contacts,
            "companies": companies,
            "engagements_v1": engagements_v1,
        },
    }


def load_token() -> str:
    token = os.environ.get("HUBSPOT_API_TOKEN") or os.environ.get("HUBSPOT_API_KEY")
    if not token:
        raise RuntimeError("HUBSPOT_API_TOKEN env var is required")
    return token.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull HubSpot CRM data for named accounts")
    parser.add_argument("companies", nargs="+", help="Company names or search tokens")
    parser.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()

    token = load_token()
    client = HubSpotClient(token)

    payload: Dict[str, Any] = {
        "generated_at": int(time.time()),
        "pipelines": client.pipelines(),
        "companies": [],
    }

    for company_query in args.companies:
        try:
            payload["companies"].append(collect_company_payload(client, company_query))
        except Exception as exc:
            payload["companies"].append({"query": company_query, "error": str(exc)})

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
