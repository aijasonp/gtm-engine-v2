#!/usr/bin/env python3
"""
Industry recovery pass for HubSpot companies missing `industry` (Jason, 2026-09-25).

Sheet-first rule: results land in a NEW tab on the audit sheet. NO HubSpot writes.

Flow:
  1. Pull companies missing industry (with domain) via windowed createdate search.
  2. Reuse meta_desc/name from output/company-cleanup/domain_results_clean.csv.
     Scrape domains not already covered (persist new scrapes to account-knowledge).
  3. Classify each company into HubSpot's industry picklist via Jev Choice.
  4. Write CSV + new sheet tab, recovered rows first.
"""
import csv, json, os, re, sys, time, calendar
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

WS = os.path.expanduser("~/.openclaw/workspace")
OUT = os.path.join(WS, "output", "company-cleanup")
AK = os.path.join(WS, "account-knowledge")
sys.path.insert(0, os.path.join(WS, "scripts", "outbound-engine"))
sys.path.insert(0, os.path.join(WS, "scripts", "company-cleanup"))

from typesafe_client import get_client  # noqa: E402
from typesafe_sdk import Choice  # noqa: E402
import scrape_free_data as sfd  # noqa: E402  (reuses scrape_domain, quarter_windows, hs_search_windowed)

HUBSPOT_TOKEN = None
for line in open(os.path.expanduser("~/.openclaw/.env")):
    if line.startswith("HUBSPOT_TOKEN="):
        HUBSPOT_TOKEN = line.strip().split("=", 1)[1]
assert HUBSPOT_TOKEN
HS = "https://api.hubapi.com"
HDR = {"Authorization": f"Bearer {HUBSPOT_TOKEN}"}

LOG = open(os.path.join(OUT, "industry_pass.log"), "a", buffering=1)
def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.write(line + "\n")


def pull_companies_missing_industry():
    base = [
        {"propertyName": "industry", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "domain", "operator": "HAS_PROPERTY"},
    ]
    props = ["name", "domain", "industry", "website", "createdate"]
    recs = []
    windows = sfd.quarter_windows()
    for i, (s, e) in enumerate(windows):
        chunk = sfd.hs_search_windowed("companies", base, props, s, e)
        recs.extend(chunk)
        log(f"  window {i+1}/{len(windows)}: +{len(chunk)} (total {len(recs)})")
    seen, out = set(), []
    for r in recs:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        p = r["properties"]
        dom = (p.get("domain") or "").strip().lower()
        if not dom:
            continue
        out.append({
            "id": r["id"],
            "domain": dom,
            "name": (p.get("name") or "").strip(),
            "website": p.get("website") or "",
        })
    return out


def get_industry_picklist():
    r = requests.get(f"{HS}/crm/v3/properties/companies/industry", headers=HDR, timeout=30)
    r.raise_for_status()
    opts = [(o["value"], o["label"]) for o in r.json().get("options", [])]
    return opts


def load_domain_cache():
    cache = {}
    path = os.path.join(OUT, "domain_results_clean.csv")
    with open(path) as f:
        for row in csv.DictReader(f):
            cache[row["domain"].strip().lower()] = {
                "name": row.get("recovered_name", "").strip(),
                "meta_desc": row.get("meta_desc", "").strip(),
                "source": row.get("source", ""),
            }
    return cache


def persist_scrape(domain, name, source, meta_desc):
    """Append-only account-knowledge retention (mirrors typesafe_client persist pattern)."""
    try:
        os.makedirs(AK, exist_ok=True)
        safe = re.sub(r"[^a-z0-9.-]", "_", domain)
        path = os.path.join(AK, f"{safe}.md")
        entry = (
            f"\n\n## Scrape — industry-pass ({time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())})\n"
            f"- **Domain:** {domain}\n"
            f"- **Recovered name:** {name or '(none)'}\n"
            f"- **Source:** {source}\n"
            f"- **Meta description:** {(meta_desc or '')[:300]}\n"
        )
        if os.path.exists(path):
            with open(path, "a") as f:
                f.write(entry)
        else:
            with open(path, "w") as f:
                f.write(f"# {domain}\n{entry}")
    except Exception as e:
        log(f"  persist warn {domain}: {e}")


def main():
    t0 = time.time()
    log("=== industry pass start ===")

    log("pulling companies missing industry...")
    comps = pull_companies_missing_industry()
    log(f"  {len(comps)} companies (domain present, industry missing)")

    log("fetching HubSpot industry picklist...")
    picklist = get_industry_picklist()
    log(f"  {len(picklist)} options")
    # criteria dict: key = value (stable id), val = label
    criteria = {v: l for v, l in picklist}
    label_by_value = dict(picklist)

    cache = load_domain_cache()
    log(f"  {len(cache)} domains cached from name pass")

    domains = sorted({c["domain"] for c in comps})
    need_scrape = [d for d in domains if d not in cache or not cache[d].get("meta_desc")]
    log(f"unique domains: {len(domains)}; need fresh scrape: {len(need_scrape)}")

    # scrape missing domains (reuse sfd.scrape_domain)
    scraped = {}
    if need_scrape:
        done = 0
        with ThreadPoolExecutor(max_workers=12) as ex:
            futs = {ex.submit(sfd.scrape_domain, d): d for d in need_scrape}
            for fut in as_completed(futs):
                d = futs[fut]
                try:
                    dom, name, src, conf, desc = fut.result()
                except Exception as e:
                    dom, name, src, conf, desc = d, None, f"error:{type(e).__name__}", None, ""
                scraped[dom] = {"name": name or "", "meta_desc": desc or "", "source": src or ""}
                if name or desc:
                    persist_scrape(dom, name, f"industry-pass:{src}", desc)
                done += 1
                if done % 200 == 0:
                    el = time.time() - t0
                    rate = done / el if el else 0
                    log(f"  scraped {done}/{len(need_scrape)} ({rate:.1f}/s)")
    log(f"scrape phase done in {(time.time()-t0)/60:.1f}m")

    # merge signal per domain
    def signal_for(dom):
        c = cache.get(dom, {})
        s = scraped.get(dom, {})
        name = c.get("name") or s.get("name") or ""
        desc = c.get("meta_desc") or s.get("meta_desc") or ""
        return name, desc

    # Jev classification
    client = get_client()
    results = {}  # domain -> (value, label, conf, evidence, status)
    todo = []
    for d in domains:
        name, desc = signal_for(d)
        if not name and not desc:
            results[d] = ("", "", "", "", "no-data")
        else:
            todo.append((d, name, desc))
    log(f"classifying {len(todo)} domains via Jev ({len(domains)-len(todo)} no-data skips)")

    ok = err = 0
    for i, (d, name, desc) in enumerate(todo):
        state = f"Company: {name or d} ({d})."
        if desc:
            state += f" Description: {desc[:400]}"
        for attempt in range(3):
            try:
                resp = client.system_one(
                    state=state,
                    questions={
                        "industry": Choice(
                            instructions="Which industry best describes this company? Pick the single best fit.",
                            criteria=criteria,
                        )
                    },
                )
                a = resp.answers["industry"]
                val = a.choice
                conf = round(getattr(a, "confidence", 0) or 0, 3)
                results[d] = (val, label_by_value.get(val, val), str(conf), desc[:120], "recovered")
                ok += 1
                break
            except Exception as e:
                if attempt == 2:
                    log(f"  jev FAIL {d}: {type(e).__name__}: {e}")
                    results[d] = ("", "", "", desc[:120], "jev-error")
                    err += 1
                else:
                    time.sleep(1.5 * (attempt + 1))
        if (i + 1) % 100 == 0:
            el = time.time() - t0
            rate = (i + 1) / el if el else 0
            eta = (len(todo) - i - 1) / rate if rate else 0
            log(f"  classified {i+1}/{len(todo)} ({rate:.1f}/s, ETA {eta/60:.1f}m)")
        time.sleep(0.12)  # ~8/s max

    log(f"classification done: {ok} ok, {err} errors, {len(domains)-len(todo)} no-data")

    # write CSV
    csv_path = os.path.join(OUT, "industry_pass_companies.csv")
    rows = []
    for c in comps:
        d = c["domain"]
        val, label, conf, ev, status = results.get(d, ("", "", "", "", "no-data"))
        name, _ = signal_for(d)
        rows.append({
            "id": c["id"], "domain": d, "name": name or c["name"],
            "industry_value": val, "industry_label": label,
            "jev_confidence": conf, "evidence": ev, "status": status,
        })
    # sort: recovered first (confidence desc), then jev-error, then no-data
    def sort_key(r):
        rank = {"recovered": 0, "jev-error": 1, "no-data": 2}.get(r["status"], 3)
        try:
            conf = -float(r["jev_confidence"] or 0)
        except ValueError:
            conf = 0
        return (rank, conf, r["domain"])
    rows.sort(key=sort_key)

    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "domain", "name", "industry_value", "industry_label",
                    "jev_confidence", "evidence", "status"])
        for r in rows:
            w.writerow([r["id"], r["domain"], r["name"], r["industry_value"],
                        r["industry_label"], r["jev_confidence"], r["evidence"], r["status"]])

    rec = sum(1 for r in rows if r["status"] == "recovered")
    log(f"DONE in {(time.time()-t0)/60:.1f}m: {rec}/{len(rows)} companies classified")
    log(f"CSV: {csv_path}")

    # machine-readable summary for the sheet writer step
    with open(os.path.join(OUT, "industry_pass_summary.json"), "w") as f:
        json.dump({
            "total_companies": len(rows),
            "recovered": rec,
            "jev_error": sum(1 for r in rows if r["status"] == "jev-error"),
            "no_data": sum(1 for r in rows if r["status"] == "no-data"),
            "unique_domains": len(domains),
            "domains_scraped_fresh": len(need_scrape),
        }, f, indent=2)


if __name__ == "__main__":
    main()
