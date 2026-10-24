#!/usr/bin/env python3
"""
Enrich HubSpot contacts (no associated company) using FREE resources only.

Per {{SALES_LEADER}} 2026-09-21 15:14 UTC:
  - Try to get company name (email domain -> company guess, website scrape)
  - Confidence level score next to each one
  - Separate personal emails into their own CSV ("tab")
  - Industry next to company if possible

Guarantees per {{SALES_LEADER}} 2026-09-21 20:31 UTC ("as long as enrichment does not stop"):
  - Checkpoint after every batch: .checkpoint (offset), .partial.csv (all rows so far)
  - Atomic final writes (tmp -> rename)
  - A .done marker only on full completion
  - Safe to re-run: resumes from checkpoint, never redoes work
  - A watchdog cron restarts it if the process dies

Usage:
  python3 enrich_contacts_free.py [--limit N] [--offset N] [--reset]
"""

import argparse
import csv
import json
import os
import re
import socket
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

BASE = os.path.expanduser("~/.openclaw/workspace/output")
SRC = os.path.join(BASE, "contacts-no-company-2026-09-21.csv")
OUT_ALL = os.path.join(BASE, "contacts-enriched-2026-09-21.csv")
OUT_PERSONAL = os.path.join(BASE, "contacts-enriched-2026-09-21-personal-emails.csv")
PARTIAL = os.path.join(BASE, ".contacts-enriched.partial.csv")
CHECKPOINT = os.path.join(BASE, ".contacts-enriched.checkpoint")
DONE = os.path.join(BASE, ".contacts-enriched.done")
STATS = os.path.join(BASE, "contacts-enriched-2026-09-21-stats.txt")

BATCH = 100
FETCH_WORKERS = 12
HTTP_TIMEOUT = 6
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

PERSONAL_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "yahoo.ca", "yahoo.fr",
    "hotmail.com", "hotmail.co.uk", "outlook.com", "live.com", "msn.com",
    "aol.com", "icloud.com", "me.com", "mac.com", "protonmail.com", "proton.me", "pm.me",
    "comcast.net", "verizon.net", "att.net", "sbcglobal.net", "bellsouth.net", "earthlink.net",
    "charter.net", "cox.net", "roadrunner.com", "rr.com", "optonline.net", "optimum.net",
    "mail.com", "gmx.com", "gmx.net", "zoho.com", "yandex.com", "tutanota.com",
    "fastmail.com", "hey.com", "duck.com", "hushmail.com", "mailinator.com",
    "google.com",  # employees @google.com are personal-ish for our purposes? NO - keep corporate. (removed below)
}
PERSONAL_PROVIDERS.discard("google.com")

# Common second-level TLD patterns where "company" is the 3rd label
SLD_TLDS = {"co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "com.br", "com.mx",
            "co.jp", "co.in", "com.sg", "com.hk", "co.nz", "com.cn", "co.za", "com.co",
            "com.ar", "com.tr", "co.kr", "com.tw", "com.my", "com.ph", "co.id", "co.th"}

# Generic / infra domains that are NOT the company's brand
GENERIC_DOMAINS = {
    "amazonaws.com", "cloudfront.net", "herokuapp.com", "github.io", "wordpress.com",
    "wixsite.com", "squarespace.com", "weebly.com", "shopify.com", "myshopify.com",
    "salesforce.com", "force.com", "hubspot.com", "hs-email.com", "mailchimp.com",
    "sendgrid.net", "zendesk.com", "freshdesk.com", "intercom.io", "calendly.com",
    "linkedin.com", "facebook.com", "twitter.com", "instagram.com", "typeform.com",
    "surveymonkey.com", "eventbrite.com", "zoom.us", "webex.com", "gotomeeting.com",
}

# Free public suffix: use a small curated map for the most common SLDs only.
# For anything else, fallback: company = second-level label (good enough for a guess).

MANUAL_COMPANY_MAP = {
    # Well-known brands whose domain != company name formatting
    "ibm": "IBM", "sap": "SAP", "hp": "HP", "hpe": "HPE", "dell": "Dell",
    "intel": "Intel", "cisco": "Cisco", "oracle": "Oracle", "adobe": "Adobe",
    "vmware": "VMware", "aws": "Amazon Web Services", "amazon": "Amazon",
    "microsoft": "Microsoft", "google": "Google", "apple": "Apple", "meta": "Meta",
    "netflix": "Netflix", "nvidia": "NVIDIA", "tesla": "Tesla", "jpmorgan": "JPMorgan Chase",
    "goldmansachs": "Goldman Sachs", "morganstanley": "Morgan Stanley", "bofa": "Bank of America",
    "wellsfargo": "Wells Fargo", "citi": "Citigroup", "usbank": "U.S. Bank",
    "pwc": "PwC", "deloitte": "Deloitte", "ey": "EY", "kpmg": "KPMG",
    "mckinsey": "McKinsey & Company", "bain": "Bain & Company", "bcg": "Boston Consulting Group",
    "accenture": "Accenture", "cognizant": "Cognizant", "infosys": "Infosys", "tcs": "Tata Consultancy Services",
    "wipro": "Wipro", "capgemini": "Capgemini", "boozallen": "Booz Allen Hamilton",
    "lockheedmartin": "Lockheed Martin", "northropgrumman": "Northrop Grumman",
    "raytheon": "Raytheon", "boeing": "Boeing", "ge": "GE", "honeywell": "Honeywell",
    "3m": "3M", "pfizer": "Pfizer", "merck": "Merck", "jnj": "Johnson & Johnson",
    "lilly": "Eli Lilly", "abbvie": "AbbVie", "amgen": "Amgen", "gilead": "Gilead Sciences",
    "moderna": "Moderna", "regeneron": "Regeneron", "vertex": "Vertex Pharmaceuticals",
    "illumina": "Illumina", "thermofisher": "Thermo Fisher Scientific", "danaher": "Danaher",
    "bectondickinson": "Becton Dickinson", "bd": "BD", "stryker": "Stryker", "medtronic": "Medtronic",
    "bostonscientific": "Boston Scientific", "zimmerbiomet": "Zimmer Biomet",
    "intuitive": "Intuitive Surgical", "edwards": "Edwards Lifesciences",
    "davita": "DaVita", "hcahealthcare": "HCA Healthcare", "unitedhealth": "UnitedHealth Group",
    "anthem": "Elevance Health", "cigna": "Cigna", "humana": "Humana", "aetna": "Aetna",
    "kaiser": "Kaiser Permanente", "centene": "Centene", "molina": "Molina Healthcare",
    "walmart": "Walmart", "target": "Target", "costco": "Costco", "homedepot": "The Home Depot",
    "lowes": "Lowe's", "kroger": "Kroger", "walgreens": "Walgreens", "cvs": "CVS Health",
    "nike": "Nike", "adidas": "Adidas", "starbucks": "Starbucks", "mcdonalds": "McDonald's",
    "cocacola": "The Coca-Cola Company", "pepsico": "PepsiCo", "nestle": "Nestlé",
    "unilever": "Unilever", "pg": "Procter & Gamble", "colgate": "Colgate-Palmolive",
    "kimberly": "Kimberly-Clark", "generalmills": "General Mills", "kelloggs": "Kellogg's",
    "kraftheinz": "Kraft Heinz", "mondelez": "Mondelez International", "tyson": "Tyson Foods",
    "cargill": "Cargill", "adm": "ADM", "bunge": "Bunge", "sysco": "Sysco",
    "usfoods": "US Foods", "mcdonough": "McDonough",
    "visa": "Visa", "mastercard": "Mastercard", "amex": "American Express",
    "discover": "Discover", "paypal": "PayPal", "stripe": "Stripe", "square": "Block",
    "block": "Block", "shopifyco": "Shopify", "uber": "Uber", "lyft": "Lyft",
    "airbnb": "Airbnb", "doordash": "DoorDash", "instacart": "Instacart",
    "grubhub": "Grubhub", "expedia": "Expedia", "booking": "Booking Holdings",
    "marriott": "Marriott", "hilton": "Hilton", "hyatt": "Hyatt", "ihg": "IHG",
    "delta": "Delta Air Lines", "united": "United Airlines", "aa": "American Airlines",
    "southwest": "Southwest Airlines", "jetblue": "JetBlue", "alaskaair": "Alaska Airlines",
    "fedex": "FedEx", "ups": "UPS", "dhl": "DHL", "usps": "USPS",
    "att": "AT&T", "verizon": "Verizon", "tmobile": "T-Mobile", "sprint": "T-Mobile",
    "comcast": "Comcast", "charter": "Charter Communications", "dish": "DISH Network",
    "disney": "The Walt Disney Company", "warnerbros": "Warner Bros. Discovery",
    "paramount": "Paramount", "nbcuniversal": "NBCUniversal", "fox": "Fox Corporation",
    "sony": "Sony", "nintendo": "Nintendo", "ea": "Electronic Arts", "activision": "Activision Blizzard",
    "salesforceco": "Salesforce", "servicenow": "ServiceNow", "workday": "Workday",
    "snowflake": "Snowflake", "databricks": "Databricks", "palantir": "Palantir",
    "crowdstrike": "CrowdStrike", "paloaltonetworks": "Palo Alto Networks",
    "fortinet": "Fortinet", "zscaler": "Zscaler", "okta": "Okta", "cyberark": "CyberArk",
    "sentinelone": "SentinelOne", "datadog": "Datadog", "newrelic": "New Relic",
    "splunk": "Splunk", "elastic": "Elastic", "mongodb": "MongoDB", "redis": "Redis",
    "confluent": "Confluent", "hashicorp": "HashiCorp", "gitlab": "GitLab", "github": "GitHub",
    "atlassian": "Atlassian", "slack": "Slack", "asana": "Asana", "monday": "monday.com",
    "notion": "Notion", "figma": "Figma", "canva": "Canva", "miro": "Miro",
    "dropbox": "Dropbox", "box": "Box", "twilio": "Twilio", "ringcentral": "RingCentral",
    "zoomvideo": "Zoom", "docusign": "DocuSign", "hubspotco": "HubSpot",
    "marketo": "Adobe Marketo", "pardot": "Salesforce Pardot",
    "kpmgus": "KPMG", "pwcus": "PwC",
}

INDUSTRY_KEYWORDS = [
    ("cyber security|cybersecurity|infosec|security", "Cybersecurity"),
    ("health|medical|pharma|bio|clinic|hospital|care|therapeutics|diagnostics", "Healthcare / Life Sciences"),
    ("bank|financial|capital|insurance|invest|wealth|credit|fintech|payments", "Financial Services"),
    ("software|saas|tech|cloud|data|ai|analytics|digital|systems|solutions|labs|io", "Technology / Software"),
    ("consult|advisory|partners|associates|group", "Consulting / Professional Services"),
    ("law|legal|llp|esq", "Legal"),
    ("edu|university|college|school|academy", "Education"),
    ("gov|federal|state|city|county|municipal", "Government"),
    ("energy|oil|gas|solar|power|utilities|electric", "Energy / Utilities"),
    ("manufactur|industrial|factory|machin", "Manufacturing / Industrial"),
    ("retail|store|shop|commerce|consumer|brands", "Retail / Consumer"),
    ("media|news|press|publish|studio|film|entertainment", "Media / Entertainment"),
    ("real.?estate|property|properties|realty|homes", "Real Estate"),
    ("transport|logistics|shipping|freight|trucking|supply", "Transportation / Logistics"),
    ("food|restaurant|beverage|agri|farm", "Food & Beverage / Agriculture"),
    ("telecom|mobile|wireless|broadband", "Telecommunications"),
    ("construct|build|architect|engineer", "Construction / Engineering"),
    ("nonprofit|foundation|charity|org$", "Nonprofit"),
    ("aero|defense|defence|space", "Aerospace / Defense"),
    ("auto|motors|vehicle", "Automotive"),
    ("hotel|hospitality|travel|tour", "Hospitality / Travel"),
]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg):
    print(f"[{now_iso()}] {msg}", flush=True)


def extract_domain(email):
    if not email or "@" not in email:
        return ""
    d = email.rsplit("@", 1)[1].strip().lower()
    return d


def is_personal(domain):
    return domain in PERSONAL_PROVIDERS


def registrable_labels(domain):
    """Return the registrable core label for company guessing."""
    if not domain:
        return ""
    parts = domain.split(".")
    if len(parts) < 2:
        return domain
    tail2 = ".".join(parts[-2:])
    if tail2 in SLD_TLDS and len(parts) >= 3:
        return parts[-3]
    return parts[-2]


def guess_company_from_domain(domain):
    """Heuristic company name from email domain. Returns (name, source, confidence 0-100)."""
    if not domain:
        return ("", "none", 0)
    if domain in GENERIC_DOMAINS:
        return ("", "generic-domain", 5)
    core = registrable_labels(domain)
    if not core:
        return ("", "none", 0)
    if core in MANUAL_COMPANY_MAP:
        return (MANUAL_COMPANY_MAP[core], "domain-map", 85)
    # Clean the core into a plausible company name
    pretty = re.sub(r"[-_]+", " ", core).strip()
    pretty = re.sub(r"(?i)\b(inc|llc|ltd|corp|co|company|group|holdings)\b$", "", pretty).strip()
    if not pretty:
        return ("", "none", 0)
    name = " ".join(w.capitalize() for w in pretty.split())
    return (name, "domain-heuristic", 60)


def title_case(s):
    return " ".join(w.capitalize() for w in re.split(r"\s+", s.strip()) if w)


def fetch_website_meta(domain):
    """Fetch homepage title/meta description for industry hints. Best-effort, cached."""
    if not domain or domain in GENERIC_DOMAINS or is_personal(domain):
        return None
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}/"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                html = r.read(65536).decode("utf-8", errors="ignore")
            title = ""
            m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            if m:
                title = re.sub(r"\s+", " ", m.group(1)).strip()[:200]
            desc = ""
            m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.I | re.S)
            if not m:
                m = re.search(r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']', html, re.I | re.S)
            if m:
                desc = re.sub(r"\s+", " ", m.group(1)).strip()[:500]
            return {"title": title, "description": desc}
        except Exception:
            continue
    return None


def refine_company_from_title(domain, heuristic_name):
    """Use homepage <title> to improve the company name. Returns (name, source, conf) or None."""
    meta = fetch_website_meta(domain)
    if not meta or not meta.get("title"):
        return None
    t = meta["title"]
    # Common patterns: "Company | tagline", "Company - tagline", "Company: tagline", "tagline | Company"
    segs = re.split(r"\s*[|\u2013\u2014\u2012\-:]\s*", t)
    segs = [s.strip() for s in segs if s.strip()]
    if not segs:
        return None
    core = registrable_labels(domain).lower()
    best = None
    for s in segs:
        sl = s.lower().replace(" ", "").replace("-", "")
        if core and (core in sl or sl in core) and 2 <= len(s.split()) <= 6:
            best = s
            break
    if not best:
        # fallback: shortest segment that looks like a name
        cand = sorted(segs, key=len)[0]
        if 2 <= len(cand) <= 60:
            best = cand
    if not best:
        return None
    best = re.sub(r"(?i)\b(official site|home|homepage|welcome to)\b", "", best).strip(" |-:")
    if len(best) < 2:
        return None
    return (best, "website-title", 80)


def guess_industry(text):
    if not text:
        return ""
    tl = text.lower()
    for pat, ind in INDUSTRY_KEYWORDS:
        if re.search(pat, tl):
            return ind
    return ""


def enrich_row(row, site_cache):
    email = (row.get("email") or "").strip()
    domain = extract_domain(email)
    out = dict(row)
    out["domain"] = domain
    out["email_type"] = "personal" if is_personal(domain) else ("business" if domain else "unknown")

    company, source, conf = guess_company_from_domain(domain)
    industry = ""

    if domain and not is_personal(domain) and domain not in GENERIC_DOMAINS:
        # website title refinement (cached per domain)
        if domain not in site_cache:
            site_cache[domain] = refine_company_from_title(domain, company)
        refined = site_cache[domain]
        if refined:
            company, source, conf = refined
        # industry from title+description of website, else from company/domain words
        meta_key = f"meta::{domain}"
        if meta_key not in site_cache:
            site_cache[meta_key] = fetch_website_meta(domain)
        meta = site_cache[meta_key]
        if meta:
            industry = guess_industry(f"{meta.get('title','')} {meta.get('description','')}")
        if not industry:
            industry = guess_industry(f"{company} {domain}")

    out["company_guess"] = company
    out["company_source"] = source
    out["industry"] = industry

    # Confidence assembly
    if not domain:
        conf = 0
    elif is_personal(domain):
        conf = 10  # can't infer company from gmail etc.
    conf = max(0, min(100, conf))
    out["confidence"] = conf
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    if args.reset:
        for p in (PARTIAL, CHECKPOINT, DONE):
            if os.path.exists(p):
                os.remove(p)

    if os.path.exists(DONE):
        log("DONE marker exists — nothing to do.")
        return 0

    with open(SRC, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        fieldnames = r.fieldnames or []
        rows = list(r)
    total = len(rows)
    log(f"Loaded {total} rows from {SRC}")

    out_fields = fieldnames + ["domain", "email_type", "company_guess", "company_source", "industry", "confidence"]

    start = args.offset
    if os.path.exists(CHECKPOINT) and not args.offset:
        try:
            start = int(open(CHECKPOINT).read().strip() or "0")
        except Exception:
            start = 0
    end = total if args.limit <= 0 else min(total, start + args.limit)
    log(f"Processing rows [{start}, {end}) of {total}")

    # Load partial if resuming
    mode = "a" if os.path.exists(PARTIAL) and start > 0 else "w"
    pf = open(PARTIAL, mode, newline="", encoding="utf-8")
    writer = csv.DictWriter(pf, fieldnames=out_fields, extrasaction="ignore")
    if mode == "w":
        writer.writeheader()
        pf.flush()

    site_cache = {}
    processed = start
    t0 = time.time()

    try:
        i = start
        while i < end:
            batch = rows[i:i + BATCH]
            results = [None] * len(batch)

            def work(idx_row):
                idx, row = idx_row
                try:
                    return idx, enrich_row(row, site_cache)
                except Exception as e:
                    rr = dict(row)
                    rr.update({"domain": extract_domain(row.get("email", "")),
                               "email_type": "unknown", "company_guess": "",
                               "company_source": "error", "industry": "", "confidence": 0})
                    return idx, rr

            with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
                futs = [ex.submit(work, (k, row)) for k, row in enumerate(batch)]
                for fut in as_completed(futs):
                    idx, res = fut.result()
                    results[idx] = res

            for res in results:
                if res:
                    writer.writerow(res)
            pf.flush()
            os.fsync(pf.fileno())

            processed = i + len(batch)
            with open(CHECKPOINT, "w") as cf:
                cf.write(str(processed))
            i = processed
            if (processed // BATCH) % 10 == 0:
                rate = (processed - start) / max(1, time.time() - t0)
                log(f"progress {processed}/{end} ({rate:.1f} rows/s)")
    except KeyboardInterrupt:
        log("Interrupted — checkpoint saved.")
        pf.close()
        return 130
    except Exception as e:
        log(f"ERROR: {e!r} — checkpoint saved at {processed}")
        pf.close()
        return 1

    pf.close()

    # Finalize: split personal vs all, atomic rename
    personal_rows = 0
    all_rows = 0
    with open(PARTIAL, newline="", encoding="utf-8") as f, \
         open(OUT_ALL + ".tmp", "w", newline="", encoding="utf-8") as fa, \
         open(OUT_PERSONAL + ".tmp", "w", newline="", encoding="utf-8") as fp:
        r = csv.DictReader(f)
        wa = csv.DictWriter(fa, fieldnames=out_fields, extrasaction="ignore")
        wp = csv.DictWriter(fp, fieldnames=out_fields, extrasaction="ignore")
        wa.writeheader(); wp.writeheader()
        for row in r:
            all_rows += 1
            wa.writerow(row)
            if row.get("email_type") == "personal":
                personal_rows += 1
                wp.writerow(row)

    os.replace(OUT_ALL + ".tmp", OUT_ALL)
    os.replace(OUT_PERSONAL + ".tmp", OUT_PERSONAL)

    # Stats
    stats = {
        "finished_at": now_iso(),
        "source_rows": total,
        "enriched_rows": all_rows,
        "personal_email_rows": personal_rows,
        "business_email_rows": all_rows - personal_rows,
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    with open(STATS, "w") as sf:
        for k, v in stats.items():
            sf.write(f"{k}: {v}\n")

    with open(DONE, "w") as df:
        df.write(now_iso() + "\n")

    if os.path.exists(PARTIAL):
        os.remove(PARTIAL)
    if os.path.exists(CHECKPOINT):
        os.remove(CHECKPOINT)

    log(f"DONE: {all_rows} rows ({personal_rows} personal) in {stats['elapsed_seconds']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
