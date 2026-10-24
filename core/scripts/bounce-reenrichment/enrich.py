#!/usr/bin/env python3
"""Bounced-contacts enrichment (2026-10-21) — MoltSets first, Clay waterfall for misses.

Sheet: 'Bounced - Needs Enrichment' tab, REDACTED_GOOGLE_ID
Columns: A Name | B Title | C Company | D LinkedIn URL | E HQ City | F HQ State |
         G Bounced Email | H Bounce Reason | I Bounce Date | J Phone |
         K Original Email Source/Confidence | L Notes

Approach (cost-savings):
  1. MoltSets business_email_by_name(full_name, domain) — 1 token, no charge on miss.
     Accept risk A/B/C. D/F = skip.
  2. For rows MoltSets misses (and rows with no clear full name/domain), fall back to
     Clay email waterfall (hot-opens wf_0tm2xtjksYGWrEVDH2S has phone only — use the
     EMAIL workflow instead: cadence wf_0tm4s54NmUS3okFGU9e... no, that's phones too).
     For email waterfall: use workbook WB1 email-enrich webhook if needed.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.expanduser("~/projects/scripts/outbound-engine"))
from moltsets_client import MoltSetsClient  # noqa: E402

SHEET_JSON = os.path.join(HERE, "sheet_raw.json")

# Known domains per company (bounce reasons + original-source notes used to confirm)
DOMAIN_OVERRIDES = {
    "acme corp": "acme.com",  # company name (lowercase) -> email domain
}

# Full names recovered from the Notes column (bounced-email rows use truncated "First L"
# placeholders; notes carry the resolved full names + LinkedIn slugs).
FULL_NAME_OVERRIDES = {
    # row_index: "First Last",  (fill from your own sheet)
}


def load_key():
    for line in open(os.path.expanduser("~/.openclaw/.env")):
        if line.startswith("MOLTSETS_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("MOLTSETS_API_KEY missing")


def load_rows():
    d = json.load(open(SHEET_JSON))
    vals = d["values"]
    out = []
    for i, r in enumerate(vals):
        if i == 0:
            continue
        row_num = i + 1
        r = r + [""] * (12 - len(r))
        company = r[2].strip()
        out.append({
            "row": row_num,
            "name_display": r[0].strip(),
            "full_name": FULL_NAME_OVERRIDES.get(row_num, r[0].strip()),
            "title": r[1].strip(),
            "company": company,
            "domain": DOMAIN_OVERRIDES.get(company.lower(), ""),
            "linkedin": r[3].strip(),
            "bounced_email": r[6].strip(),
            "bounce_reason": r[7].strip(),
            "phone_existing": r[9].strip(),
        })
    return out


def main():
    rows = load_rows()
    print(f"rows: {len(rows)}", flush=True)
    ms = MoltSetsClient(load_key())

    try:
        acct = ms.get_account()
        print("moltsets acct:", json.dumps(acct)[:240], flush=True)
    except Exception as e:
        print("acct check failed (continuing):", e, flush=True)

    hits = 0
    for r in rows:
        r.update({"ms_email": "", "ms_risk": "", "ms_linkedin": "", "ms_status": ""})
        if not r["domain"]:
            r["ms_status"] = "no_domain"
            continue
        try:
            res = ms.business_email_by_name(r["full_name"], r["domain"])
        except Exception as e:
            r["ms_status"] = f"error:{type(e).__name__}:{e}"
            print(f"  ERR row {r['row']} {r['full_name']}: {e}", flush=True)
            continue
        st = res.get("status")
        if st == "ok":
            rr = res.get("results") or {}
            r["ms_email"] = (rr.get("email") or "").strip().lower()
            r["ms_risk"] = rr.get("risk_score") or ""
            r["ms_linkedin"] = (rr.get("linkedin_url") or "").strip()
            if r["ms_risk"] in ("A", "B", "C"):
                r["ms_status"] = "ok"
                hits += 1
            else:
                r["ms_status"] = f"low_risk:{r['ms_risk']}"
                r["ms_email"] = ""
        else:
            r["ms_status"] = st or "miss"
        print(f"  row {r['row']:>2} {r['full_name']:<22} {r['domain']:<28} -> {r['ms_status']}  {r['ms_email']} {r['ms_risk']}", flush=True)
        time.sleep(0.25)

    print(f"moltsets accepted: {hits}/{len(rows)}", flush=True)
    json.dump(rows, open(os.path.join(HERE, "moltsets_results.json"), "w"), indent=2)

    misses = [r for r in rows if r["ms_status"] != "ok"]
    print(f"misses -> Clay waterfall: {len(misses)}", flush=True)
    for r in misses:
        print(f"  MISS row {r['row']} {r['full_name']} ({r['domain']}) status={r['ms_status']}", flush=True)


if __name__ == "__main__":
    main()
