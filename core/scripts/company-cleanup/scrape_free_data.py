#!/usr/bin/env python3
"""
Free-data scrape pass for HubSpot company cleanup (Jason, 2026-09-24).

Scope:
  1. Companies missing `name` (must have domain)
  2. Contacts missing `company` text field (corporate email domains only)

Dedupes to unique domains, scrapes each once over plain HTTP, extracts free
signals: company name (og:site_name / JSON-LD / <title> / copyright footer),
plus meta description as raw material for a later industry pass.

Output CSVs in output/company-cleanup/. Nothing writes to HubSpot.
"""
import csv, json, os, re, ssl, sys, time, html, calendar
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests, urllib3
urllib3.disable_warnings()

WS = os.path.expanduser("~/.openclaw/workspace")
OUT = os.path.join(WS, "output", "company-cleanup")
os.makedirs(OUT, exist_ok=True)

HUBSPOT_TOKEN = None
for line in open(os.path.expanduser("~/.openclaw/.env")):
    if line.startswith("HUBSPOT_TOKEN="):
        HUBSPOT_TOKEN = line.strip().split("=", 1)[1]
assert HUBSPOT_TOKEN, "no HUBSPOT_TOKEN"

HS = "https://api.hubapi.com"
HDR = {"Authorization": f"Bearer {HUBSPOT_TOKEN}"}

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/10.0.0.1 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

FREE_PARKING = re.compile(r"(domain is for sale|buy this domain|parked free|hugedomains|sedo\.com|afternic|dan\.com|undeveloped|this domain may be for sale)", re.I)

def hs_search_pages(obj, filters, props):
    url = f"{HS}/crm/v3/objects/{obj}/search"
    body = {"filterGroups": [{"filters": filters}], "properties": props, "limit": 100}
    out, after = [], None
    while True:
        b = dict(body)
        if after:
            b["after"] = after
        for attempt in range(4):
            try:
                r = requests.post(url, headers=HDR, json=b, timeout=30)
                if r.status_code == 429:
                    time.sleep(2 * (attempt + 1)); continue
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 3: raise
                time.sleep(2 * (attempt + 1))
        j = r.json()
        out.extend(j.get("results", []))
        after = j.get("paging", {}).get("next", {}).get("after")
        if not after:
            return out
        time.sleep(0.12)

def hs_search_windowed(obj, base_filters, props, start_ms, end_ms, depth=0):
    filters = base_filters + [
        {"propertyName": "createdate", "operator": "GTE", "value": str(start_ms)},
        {"propertyName": "createdate", "operator": "LT", "value": str(end_ms)},
    ]
    res = hs_search_pages(obj, filters, props)
    if len(res) >= 10000 and depth < 12:
        mid = (start_ms + end_ms) // 2
        return (hs_search_windowed(obj, base_filters, props, start_ms, mid, depth + 1) +
                hs_search_windowed(obj, base_filters, props, mid, end_ms, depth + 1))
    return res

def quarter_windows():
    # 2019-01-01 .. 2026-10-01 quarterly, plus catch-all before 2019
    wins = [(0, 1546300800000)]
    for y in range(2019, 2027):
        for q_start in (1, 4, 7, 10):
            s = calendar.timegm((y, q_start, 1, 0, 0, 0)) * 1000
            ey, em = (y + 1, 1) if q_start == 10 else (y, q_start + 3)
            e = calendar.timegm((ey, em, 1, 0, 0, 0)) * 1000
            if s < 1790304000000:  # 2026-09-25-ish cutoff handled by final window
                wins.append((s, min(e, 1790304000000)))
    # dedupe + sort
    wins = sorted(set(wins))
    return wins

def pull_companies_missing_name():
    base = [
        {"propertyName": "name", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "domain", "operator": "HAS_PROPERTY"},
    ]
    props = ["name", "domain", "industry", "website", "hubspot_owner_id", "createdate"]
    recs = []
    for s, e in quarter_windows():
        recs.extend(hs_search_windowed("companies", base, props, s, e))
    seen, out = set(), []
    for r in recs:
        if r["id"] in seen: continue
        seen.add(r["id"])
        p = r["properties"]
        out.append(("company", r["id"], (p.get("domain") or "").strip().lower(), p.get("website") or ""))
    return out

def pull_contacts_missing_company():
    base = [
        {"propertyName": "company", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "email", "operator": "HAS_PROPERTY"},
    ]
    props = ["email", "company", "lifecyclestage", "hubspot_owner_id", "associatedcompanyid", "createdate"]
    FREE = {"gmail.com","yahoo.com","hotmail.com","outlook.com","aol.com","icloud.com","msn.com","live.com","me.com","comcast.net","verizon.net","att.net","sbcglobal.net","earthlink.net","mail.com","protonmail.com","ymail.com","googlemail.com","charter.net","cox.net","bellsouth.net","mac.com","rocketmail.com","gmx.com","zoho.com","fastmail.com","tutanota.com","proton.me","hey.com","pm.me","hotmail.co.uk","yahoo.co.uk","btinternet.com","shaw.ca","rogers.com","telus.net","sympatico.ca","videotron.ca","centurylink.net","frontier.com","windstream.net","optonline.net","optimum.net","juno.com","netzero.net","usa.net","rediffmail.com","yahoo.ca","hotmail.fr","orange.fr","free.fr","web.de","gmx.de","t-online.de","libero.it","virgilio.it","qq.com","163.com","naver.com","daum.net","hanmail.net"}
    recs = []
    windows = quarter_windows()
    for i, (s, e) in enumerate(windows):
        chunk = hs_search_windowed("contacts", base, props, s, e)
        recs.extend(chunk)
        print(f"  contacts window {i+1}/{len(windows)}: +{len(chunk)} (total {len(recs)})", flush=True)
    seen, out = set(), []
    for r in recs:
        if r["id"] in seen: continue
        seen.add(r["id"])
        p = r["properties"]
        em = (p.get("email") or "").strip().lower()
        if "@" not in em: continue
        dom = em.split("@", 1)[1]
        if dom in FREE: continue
        out.append(("contact", r["id"], dom, em))
    return out

# ---------- scraping ----------

def fetch(url):
    try:
        r = requests.get(url, headers=UA, timeout=(6, 10), verify=False, allow_redirects=True)
        if r.status_code >= 400:
            return None, r.status_code
        ct = r.headers.get("content-type", "")
        if ct and "html" not in ct and "text" not in ct:
            return None, f"ct:{ct.split(';')[0]}"
        return r.text[:400_000], r.status_code
    except Exception as e:
        return None, type(e).__name__

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
OG_SITE = re.compile(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)', re.I)
OG_SITE2 = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:site_name["\']', re.I)
META_DESC = re.compile(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', re.I)
META_DESC2 = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', re.I)
OG_DESC = re.compile(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)', re.I)
JSONLD_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S)
COPY_RE = re.compile(r"(?:©|&copy;|&#169;|copyright)\s*(?:\(c\))?\s*\d{2,4}?\s*(?:[-–]\s*\d{2,4})?\s*([A-Z][A-Za-z0-9&.,'’\- ]{2,60})", re.I)
BAD_TITLE = re.compile(r"^(home|welcome|index|untitled|403|404|access denied|just a moment|attention required|security check|loading)", re.I)

def clean_name(n):
    if not n: return None
    n = html.unescape(n).strip()
    n = re.sub(r"\s+", " ", n)
    n = re.split(r"\s+[|»—–-]\s+", n)[0].strip()
    n = n.strip(" |»—–-·•")
    if len(n) < 2 or len(n) > 80: return None
    if BAD_TITLE.match(n): return None
    return n

def extract(html_text):
    """returns (name, source, meta_desc)"""
    if not html_text: return None, None, ""
    if FREE_PARKING.search(html_text[:5000]):
        return None, "parked", ""
    desc = ""
    for rx in (META_DESC, META_DESC2, OG_DESC):
        m = rx.search(html_text)
        if m:
            desc = html.unescape(m.group(1)).strip()[:300]
            break
    for rx in (OG_SITE, OG_SITE2):
        m = rx.search(html_text)
        if m:
            n = clean_name(m.group(1))
            if n: return n, "og:site_name", desc
    for m in JSONLD_RE.finditer(html_text):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                t = item.get("@type", "")
                if (t == "Organization" or (isinstance(t, list) and "Organization" in t)) and item.get("name"):
                    n = clean_name(str(item["name"]))
                    if n: return n, "json-ld", desc
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
    m = TITLE_RE.search(html_text)
    if m:
        n = clean_name(m.group(1))
        if n: return n, "title", desc
    m = COPY_RE.search(html_text)
    if m:
        n = clean_name(m.group(1))
        if n: return n, "copyright", desc
    return None, "no-signal", desc

def scrape_domain(dom):
    dom = dom.strip().lower().lstrip("*.")
    if not dom or "." not in dom:
        return dom, None, "bad-domain", None, ""
    tried = []
    for url in (f"https://{dom}", f"https://www.{dom}", f"http://{dom}"):
        body, status = fetch(url)
        tried.append(str(status))
        if body:
            name, src, desc = extract(body)
            if name:
                conf = {"og:site_name": "high", "json-ld": "high", "title": "medium", "copyright": "low"}.get(src, "low")
                return dom, name, src, conf, desc
            if src == "parked":
                return dom, None, "parked", None, ""
            return dom, None, "no-signal", None, desc
    return dom, None, "unreachable:" + "/".join(tried), None, ""

def main():
    t0 = time.time()
    print("pulling companies missing name...", flush=True)
    comps = pull_companies_missing_name()
    print(f"  {len(comps)} companies (domain present, name missing)", flush=True)
    print("pulling contacts missing company text...", flush=True)
    conts = pull_contacts_missing_company()
    print(f"  {len(conts)} contacts (corporate email, company text missing)", flush=True)

    with open(os.path.join(OUT, "records_companies.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["object", "id", "domain", "website"]); w.writerows(comps)
    with open(os.path.join(OUT, "records_contacts.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["object", "id", "domain", "email"]); w.writerows(conts)

    domains = sorted({d for _, _, d, _ in comps + conts if d})
    print(f"unique domains to scrape: {len(domains)}", flush=True)

    results = {}
    done = 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(scrape_domain, d): d for d in domains}
        for fut in as_completed(futs):
            d = futs[fut]
            try:
                dom, name, src, conf, desc = fut.result()
            except Exception as e:
                dom, name, src, conf, desc = d, None, f"error:{type(e).__name__}", None, ""
            results[dom] = (name, src, conf, desc)
            done += 1
            if done % 250 == 0:
                el = time.time() - t0
                rate = done / el if el else 0
                eta = (len(domains) - done) / rate if rate else 0
                print(f"  scraped {done}/{len(domains)} ({rate:.1f}/s, ETA {eta/60:.1f}m)", flush=True)

    with open(os.path.join(OUT, "domain_results.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["domain", "recovered_name", "source", "confidence", "meta_desc"])
        for d in domains:
            n, s, c, desc = results.get(d, (None, None, None, ""))
            w.writerow([d, n or "", s or "", c or "", desc or ""])

    def map_rows(recs):
        rows = []
        for obj, rid, dom, extra in recs:
            n, s, c, _ = results.get(dom, (None, None, None, ""))
            rows.append([obj, rid, dom, extra, n or "", s or "", c or ""])
        return rows

    with open(os.path.join(OUT, "recovered_companies.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["object", "id", "domain", "website", "recovered_name", "source", "confidence"])
        w.writerows(map_rows(comps))
    with open(os.path.join(OUT, "recovered_contacts.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["object", "id", "domain", "email", "recovered_name", "source", "confidence"])
        w.writerows(map_rows(conts))

    got = sum(1 for v in results.values() if v[0])
    parked = sum(1 for v in results.values() if v[1] == "parked")
    print(f"DONE in {(time.time()-t0)/60:.1f}m: names for {got}/{len(domains)} domains ({parked} parked)", flush=True)

if __name__ == "__main__":
    main()
