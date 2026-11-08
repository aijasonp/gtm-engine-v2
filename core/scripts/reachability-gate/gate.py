#!/usr/bin/env python3
"""gate.py: reachability gate between Clay enrichment and Smartlead enrollment.

Every lead that comes out of Clay gets an A-F email grade from MoltSets and a route.
Nothing is deleted: a dead mailbox is a routing decision, not a dead contact.

  A/B same domain     -> send.csv              (Smartlead, main inboxes)
  C catch-all         -> send_low_volume.csv   (Smartlead, isolated low-volume pool)
  D hard invalid      -> linkedin.csv          (LinkedIn first, then the phone waterfall)
  F / not in graph    -> second pass, then linkedin.csv or hold.csv
  person moved        -> resource.csv          (re-source at the new company, skip the stale email)
  free-mail / cross-domain -> hold.csv          (human review)

Waterfall per lead (stops as soon as it has a grade):
  1. reverse_linkedin_lookup on the LinkedIn URL: current company (job-change check) + graded email
  2. reverse_email_lookup on the email
  3. --second-pass: search_business_profile_by_name {name, company: domain} on silence or F.
     Only a same-domain A/B result with a matching name is adopted.
  4. linkedin_to_best_email for LinkedIn-only rows

If the input carries an SMTP verifier verdict (ZeroBounce, NeverBounce, MillionVerifier, Bouncer),
every row also gets a delta class showing how MoltSets moved it against that verdict.

Grades are cached in $GTM_DATA_DIR/reachability.db (default ~/.gtm/data) for --max-age-days, so a
lead that comes back through dispatch next week is not re-spent. Every API call is logged there too.

  python3 gate.py clay_export.csv                      # grade + route, write CSVs
  python3 gate.py clay_export.csv --second-pass        # recover F / 404 rows by name + domain
  python3 gate.py clay_export.json --dry-run           # plan only, no API spend
  python3 gate.py clay_export.csv --sheet              # also build the color-coded review sheet
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import moltsets_client as M  # noqa: E402
from reachability import classify, companies_match, delta_class, norm_verifier_status, profile_decision  # noqa: E402

ROUTE_FILES = {
    "email": "send.csv",
    "email_low_volume": "send_low_volume.csv",
    "linkedin": "linkedin.csv",
    "linkedin_then_phone": "linkedin.csv",
    "resource": "resource.csv",
    "hold": "hold.csv",
    "second_pass": "hold.csv",
}

# Header aliases so Clay, HubSpot, Apollo and hand-built exports all load without a mapping step.
ALIASES = {
    "email": ("email", "work_email", "business_email", "email_address", "Email", "Work Email"),
    "first_name": ("first_name", "firstname", "First Name", "first"),
    "last_name": ("last_name", "lastname", "Last Name", "last"),
    "full_name": ("full_name", "name", "Name", "Full Name"),
    "company": ("company", "company_name", "Company", "Company Name", "organization"),
    "domain": ("domain", "company_domain", "website", "Company Domain", "Website"),
    "linkedin_url": ("linkedin_url", "linkedin", "hs_linkedin_url", "LinkedIn URL", "LinkedIn", "person_linkedin_url"),
    "title": ("title", "job_title", "jobtitle", "Title", "Job Title"),
    "verifier_status": ("verifier_status", "zb_status", "zerobounce_status", "verification_status",
                        "neverbounce_status", "email_status"),
}

OUT_FIELDS = ["first_name", "last_name", "title", "company", "domain", "linkedin_url", "email", "list_email",
              "grade", "verdict", "tier", "route", "still_at_company", "molt_current_company", "corrected",
              "verifier_status", "delta_class", "graded_by", "graded_at", "from_cache"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_domain(value: str) -> str:
    d = (value or "").strip().lower()
    for prefix in ("https://", "http://"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    d = d.split("/")[0]
    return d[4:] if d.startswith("www.") else d


def normalize_row(raw: dict) -> dict:
    """Map any export's headers onto the gate's field names. Unknown columns pass through untouched."""
    row = {}
    lower = {str(k).strip().lower(): v for k, v in raw.items()}
    for field, names in ALIASES.items():
        val = ""
        for n in names:
            if n in raw and str(raw[n] or "").strip():
                val = str(raw[n]).strip()
                break
            if n.lower() in lower and str(lower[n.lower()] or "").strip():
                val = str(lower[n.lower()]).strip()
                break
        row[field] = val
    if row["full_name"] and not (row["first_name"] or row["last_name"]):
        parts = row["full_name"].split()
        row["first_name"], row["last_name"] = parts[0], " ".join(parts[1:])
    row["email"] = row["email"].lower()
    row["domain"] = clean_domain(row["domain"]) or (M.dom(row["email"]) if M.dom(row["email"]) not in M.FREEMAIL else "")
    row["_raw"] = raw
    return row


def load_leads(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            data = data.get("leads") or data.get("rows") or data.get("data") or []
        return [normalize_row(r) for r in data if isinstance(r, dict)]
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [normalize_row(r) for r in csv.DictReader(f)]


def cache_key(row: dict) -> str:
    return (row.get("linkedin_url") or "").rstrip("/").lower() or row.get("email", "")


# ----------------------------------------------------------------------------- the waterfall
def grade_row(row: dict, call, second_pass: bool = False, budget: M.Budget | None = None, log=None) -> dict:
    """Run the waterfall for one normalized lead. `call(endpoint, body) -> (status, results, metadata)`.
    Pure apart from `call` and `log`, so it runs offline in tests with a fake caller."""
    budget = budget or M.Budget()
    email, li = row.get("email", ""), row.get("linkedin_url", "")
    grade, molt_email, graded_by, still, molt_company, sp_decision = "", "", "", "unknown", "", ""
    calls = 0

    def do(endpoint, body):
        nonlocal calls
        st, res, md = call(endpoint, body)
        calls += 1
        if log:
            budget.absorb(log(endpoint, body, st, res, md))
        return st, res

    # 1. LinkedIn URL: employment check + first grading pass
    if li and budget.records_ok():
        st, res = do("reverse_linkedin_lookup", {"linkedin_url": li})
        if st == 200 and res:
            cname, cdom = M.company_of(res)
            molt_company = cname or cdom
            if cname or cdom:
                still = companies_match(row.get("company"), cname, row.get("domain"), cdom)
            if M.email_of(res) and M.grade_of(res):
                grade, molt_email, graded_by = M.grade_of(res), M.email_of(res), "reverse_linkedin_lookup"

    if still != "moved":
        # 2. the email itself
        if email and M.dom(email) not in M.FREEMAIL and not grade and budget.records_ok():
            st, res = do("reverse_email_lookup", {"email": email})
            if st == 200 and res:
                grade, molt_email, graded_by = M.grade_of(res), M.email_of(res) or email, "reverse_email_lookup"
        # 3. second pass on silence or F. Never on D: D is an answer.
        if second_pass and (not grade or grade == "F") and row.get("domain") and budget.records_ok():
            name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
            if name:
                st, res = do("search_business_profile_by_name", {"name": name, "company": row["domain"]})
                sp_decision, _ = profile_decision(res if st == 200 else {}, st, row["domain"], "",
                                                  row.get("first_name", ""), row.get("last_name", ""))
                if sp_decision in ("accept_same_domain", "risky_same_domain"):
                    grade = M.grade_of(res) or "F"
                    molt_email, graded_by = M.email_of(res), "search_business_profile_by_name"
                elif sp_decision in ("profile_no_email", "review_cross_domain"):
                    grade = grade or "F"
        # 4. LinkedIn-only rows
        if li and not email and not grade and budget.records_ok():
            st, res = do("linkedin_to_best_email", {"linkedin_url": li})
            if st == 200 and M.email_of(res):
                grade, molt_email, graded_by = M.grade_of(res), M.email_of(res), "linkedin_to_best_email"

    final_email = email or molt_email
    corrected = bool(molt_email and email and molt_email != email)
    if corrected and grade in ("A", "B") and M.dom(molt_email) == row.get("domain"):
        final_email = molt_email
    verdict, tier, route = classify(final_email, grade, row.get("domain"), has_linkedin=bool(li),
                                    second_pass_done=bool(sp_decision), still_at_company=still)
    if tier == "T1_send" and corrected:
        verdict, tier = "corrected", "T1_send_corrected"
    if route == "second_pass" and not second_pass:
        route = "linkedin" if li else "hold"
    vstat = norm_verifier_status(row.get("verifier_status"))
    dc = delta_class(vstat, grade, "", sp_decision, "yes" if corrected else "no", still) if vstat else ""
    return {"email": final_email, "list_email": email, "grade": grade, "verdict": verdict, "tier": tier,
            "route": route, "still_at_company": still, "molt_current_company": molt_company,
            "corrected": "yes" if corrected else "no", "verifier_status": vstat, "delta_class": dc,
            "graded_by": graded_by, "second_pass_decision": sp_decision, "calls": calls, "graded_at": now()}


# ----------------------------------------------------------------------------- cache + ledger
def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    con.execute("PRAGMA journal_mode = WAL;")
    M.ensure_log(con)
    con.execute("CREATE TABLE IF NOT EXISTS graded (key TEXT PRIMARY KEY, result TEXT, graded_at TEXT)")
    con.commit()
    return con


def cached(con, key: str, max_age_days: int) -> dict | None:
    if not key or max_age_days <= 0:
        return None
    r = con.execute("SELECT result, graded_at FROM graded WHERE key=?", (key,)).fetchone()
    if not r:
        return None
    try:
        when = datetime.fromisoformat(r[1])
    except ValueError:
        return None
    if datetime.now(timezone.utc) - when > timedelta(days=max_age_days):
        return None
    return json.loads(r[0])


def store(con, key: str, result: dict) -> None:
    if key:
        con.execute("INSERT OR REPLACE INTO graded (key, result, graded_at) VALUES (?,?,?)",
                    (key, json.dumps(result), result["graded_at"]))
        con.commit()


# ----------------------------------------------------------------------------- outputs
def write_outputs(out_dir: Path, rows: list[dict]) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        buckets.setdefault(ROUTE_FILES.get(r["route"], "hold.csv"), []).append(r)
    written = {}
    extra = sorted({k for r in rows for k in r.get("_raw", {}) if k not in OUT_FIELDS})
    for name, items in list(buckets.items()) + [("all.csv", rows)]:
        with (out_dir / name).open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=OUT_FIELDS + extra, extrasaction="ignore")
            w.writeheader()
            for r in items:
                w.writerow({**{k: v for k, v in r.get("_raw", {}).items() if k in extra}, **r})
        written[name] = len(items)
    return written


def summarize(rows: list[dict]) -> dict:
    out: dict = {"leads": len(rows), "by_route": {}, "by_grade": {}, "by_delta": {}, "api_calls": 0, "from_cache": 0}
    for r in rows:
        out["by_route"][r["route"]] = out["by_route"].get(r["route"], 0) + 1
        g = r["grade"] or "-"
        out["by_grade"][g] = out["by_grade"].get(g, 0) + 1
        if r.get("delta_class"):
            out["by_delta"][r["delta_class"]] = out["by_delta"].get(r["delta_class"], 0) + 1
        out["api_calls"] += int(r.get("calls") or 0)
        out["from_cache"] += 1 if r.get("from_cache") == "yes" else 0
    return out


def build_review_sheet(rows: list[dict], summary: dict, key: str | None) -> str:
    sys.path.insert(0, str(HERE.parents[1] / "lib"))
    import sheet_engine as SE
    cols = [c for c in OUT_FIELDS if any(c in r for r in rows)]
    grade_cf = {"type": "map", "col": "grade", "map": {"A": SE.GREEN, "B": SE.GREEN_LT, "C": SE.YELLOW,
                                                       "D": SE.RED, "F": SE.GREY}}
    route_cf = {"type": "map", "col": "route", "map": {"email": SE.GREEN, "email_low_volume": SE.YELLOW,
                                                       "linkedin": SE.BLUE, "linkedin_then_phone": SE.BLUE,
                                                       "resource": SE.ORANGE, "hold": SE.GREY}}
    tabs = [{"title": t, "df": [r for r in rows if not rs or r["route"] in rs], "cols": cols,
             "cf": [grade_cf, route_cf]}
            for t, rs in (("Send", ["email"]), ("Send Low Volume", ["email_low_volume"]),
                          ("LinkedIn", ["linkedin", "linkedin_then_phone"]), ("Re-source", ["resource"]),
                          ("Hold", ["hold", "second_pass"]), ("All Leads", None))]
    entries = [{"kind": "section", "label": "Routes"}]
    entries += [{"kind": "kpi", "label": k, "value": v} for k, v in sorted(summary["by_route"].items())]
    entries += [{"kind": "section", "label": "Grades"}]
    entries += [{"kind": "kpi", "label": k, "value": v} for k, v in sorted(summary["by_grade"].items())]
    if summary["by_delta"]:
        entries += [{"kind": "section", "label": "Verifier vs MoltSets"}]
        entries += [{"kind": "kpi", "label": k, "value": v} for k, v in sorted(summary["by_delta"].items())]
    url, _ = SE.build({"title": f"Reachability gate {datetime.now():%Y-%m-%d}", "key": key,
                       "dashboard": {"title": "Dashboard", "subtitle": {"title": "Reachability gate",
                                     "sub": f"{summary['leads']} leads, {summary['api_calls']} API calls"},
                                     "entries": entries},
                       "tabs": tabs})
    return url


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path, help="Clay / HubSpot / Apollo export (.csv or .json)")
    ap.add_argument("--out-dir", type=Path, default=None, help="default ./reachability-out/YYYYMMDD")
    ap.add_argument("--second-pass", action="store_true", help="name + domain recovery on F / 404")
    ap.add_argument("--max-age-days", type=int, default=30, help="reuse cached grades younger than this (0 = never)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true", help="plan only, no API spend")
    ap.add_argument("--sheet", action="store_true", help="also build the color-coded review sheet")
    ap.add_argument("--sheet-key", default=None, help="rebuild this existing sheet in place")
    args = ap.parse_args(argv)

    leads = load_leads(args.input)
    if args.limit:
        leads = leads[: args.limit]
    out_dir = args.out_dir or Path.cwd() / "reachability-out" / datetime.now().strftime("%Y%m%d")
    data_dir = Path(os.environ.get("GTM_DATA_DIR") or Path.home() / ".gtm" / "data").expanduser()
    con = open_db(Path(os.environ.get("REACHABILITY_DB") or data_dir / "reachability.db"))

    todo = [r for r in leads if not cached(con, cache_key(r), args.max_age_days)]
    print(f"{len(leads)} leads, {len(leads) - len(todo)} cached, {len(todo)} to grade "
          f"(second_pass={'on' if args.second_pass else 'off'})")
    if args.dry_run:
        for r in todo[:25]:
            print(f"  would grade: {r['first_name']} {r['last_name'][:1]}. @ {r['domain'] or '-'}  "
                  f"li={'yes' if r['linkedin_url'] else 'no'} email={'yes' if r['email'] else 'no'}")
        return 0
    if todo and not M.get_key():
        sys.exit("MOLTSETS_API_KEY not set: export it or add it to GTM_ENV_FILE")

    budget = M.Budget()
    log = lambda ep, body, st, res, md: M.log_call(con, ep, body, st, res, md, note="reachability-gate")  # noqa: E731
    results = []
    stopped = False
    for i, row in enumerate(leads, 1):
        key = cache_key(row)
        hit = cached(con, key, args.max_age_days)
        if hit:
            res = {**hit, "from_cache": "yes", "calls": 0}
        elif stopped or not budget.records_ok():
            stopped = True
            res = {"email": row["email"], "list_email": row["email"], "grade": "", "verdict": "not_graded",
                   "tier": "HOLD_review", "route": "hold", "still_at_company": "unknown", "graded_at": now(),
                   "graded_by": "floor_guard", "calls": 0}
        else:
            res = grade_row(row, lambda ep, body: (M.pause(), M.call(ep, body))[1], args.second_pass, budget, log)
            store(con, key, res)
            res["from_cache"] = "no"
        merged = {**{k: row.get(k, "") for k in ("first_name", "last_name", "title", "company", "domain",
                                                 "linkedin_url")}, **res, "_raw": row["_raw"]}
        results.append(merged)
        print(f"[{i}/{len(leads)}] {res['grade'] or '-'} {res['tier']:18} {res['route']:18} "
              f"{(row['first_name'] or '?')[:14]:14} {row['domain'][:28]}")
    if stopped:
        print(f"! floor guard: records_remaining_5h={budget.records_5h}. Ungraded rows were routed to hold.csv.")

    summary = summarize(results)
    summary.update(ran_at=now(), input=str(args.input), records_remaining_5h=budget.records_5h,
                   files=write_outputs(out_dir, results))
    if args.sheet:
        summary["sheet_url"] = build_review_sheet(results, summary, args.sheet_key)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ("by_route", "by_grade", "files")}, indent=2))
    print(f"wrote {out_dir}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
