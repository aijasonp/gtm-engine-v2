#!/usr/bin/env python3
"""Daily GTM Report Generator.
Sources: Google Calendar (primary meetings), HubSpot (company metrics + Clay enrichment proxy),
         Smartlead (outbound sends/replies), Google Sheets (events).
Output: full GTM machine rundown + live TLDR with suggested actions.
"""
import json, os, urllib.request, time, subprocess, base64
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

# --- Load env ---------------------------------------------------------------
_ENV = {}
_env_path = os.path.expanduser('~/.openclaw/.env')
if os.path.isfile(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                _ENV[k] = v.strip().strip('\'"')

def env(k):
    return os.environ.get(k, _ENV.get(k, ''))

# --- HTTP helpers ------------------------------------------------------
def http_get(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except Exception as e:
        return {"_error": str(e)}

def hs_post(path, data):
    try:
        tok = env('HUBSPOT_TOKEN')
        req = urllib.request.Request(
            f'https://api.hubapi.com{path}',
            data=json.dumps(data).encode(),
            headers={'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json',
                     'User-Agent': 'Mozilla/5.0'}
        )
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except Exception as e:
        return {"_error": str(e)}

def gwsg_json(sheet_id, range_):
    result = subprocess.run(
        ['gwsg', 'sheets', '+read', '--spreadsheet', sheet_id, '--range', range_, '--format', 'json'],
        capture_output=True, text=True, timeout=30
    )
    try:
        return json.loads(result.stdout)
    except Exception:
        return {}

def gwsg_calendar_events(cal_email, tmin, tmax):
    params = json.dumps({
        "calendarId": cal_email, "timeMin": tmin, "timeMax": tmax,
        "singleEvents": True, "maxResults": 250
    })
    result = subprocess.run(
        ['gwsg', 'calendar', 'events', 'list', '--params', params, '--format', 'json'],
        capture_output=True, text=True, timeout=60
    )
    try:
        return json.loads(result.stdout).get('items', [])
    except Exception:
        return []

# --- Smartlead --------------------------------------------------------
SL_BASE = 'https://server.smartlead.ai/api/v1'
sl_key = env('SMARTLEAD_API_KEY')
SL_AUTH = '?api_key=' + sl_key

camps = http_get(SL_BASE + '/campaigns' + SL_AUTH)
if isinstance(camps, dict) and camps.get('_error'):
    camps = []
camp_list = camps if isinstance(camps, list) else camps.get('data', []) if isinstance(camps, dict) else []

active_camps = 0
total_sent = 0
total_replies = 0
total_bounces = 0
clay_sent = 0
clay_replies = 0
CLAY_CAMPS = {'0000000', '0000000', '0000000'}  # WB1, WB3, WB4

for c in camp_list:
    cid = str(c.get('id', ''))
    if c.get('status') in ('ACTIVE', 'RUNNING'):
        active_camps += 1
    stats = http_get(SL_BASE + '/campaigns/' + cid + '/analytics' + SL_AUTH)
    if isinstance(stats, dict) and '_error' not in stats:
        s = int(stats.get('sent_count', 0) or 0)
        r = int(stats.get('reply_count', 0) or 0)
        b = int(stats.get('bounce_count', 0) or 0)
        total_sent += s
        total_replies += r
        total_bounces += b
        if cid in CLAY_CAMPS:
            clay_sent += s
            clay_replies += r
    time.sleep(0.15)

reply_rate = round((total_replies / total_sent) * 100, 2) if total_sent else 0
bounce_rate = round((total_bounces / total_sent) * 100, 2) if total_sent else 0

# --- WoW history store (seed from today on first run) -------------------
now = datetime.now(timezone.utc)
seven_days_iso = (now - timedelta(days=7)).isoformat()
HIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gtm-history.json')

def load_history():
    try:
        with open(HIST_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_history(h):
    try:
        with open(HIST_FILE, 'w') as f:
            json.dump(h, f, indent=2)
    except Exception:
        pass

def wow_trend(key, current):
    """Return (arrow, pct_change) vs last stored value for key, or (None, None) if no prior."""
    hist = load_history()
    prev = hist.get(key)
    if prev is None:
        return None, None
    if prev == 0:
        return ('up' if current > 0 else 'flat', None)
    pct = round(((current - prev) / prev) * 100, 1)
    arrow = 'up' if pct > 2 else ('down' if pct < -2 else 'flat')
    return arrow, pct

def arrow_sym(a):
    return {'up': ':arrow_up:', 'down': ':arrow_down:', 'flat': ':arrow_right:'}.get(a, '')

# --- Clay raw enrichment (rolling 7d) via HubSpot contacts created ---------
clay_contacts = hs_post('/crm/v3/objects/contacts/search', {
    "filterGroups": [{"filters": [{"propertyName": "createdate", "operator": "GTE", "value": seven_days_iso}]}],
    "properties": ["createdate"], "limit": 1
})
clay_enriched_7d = clay_contacts.get('total', 0) if isinstance(clay_contacts, dict) else 0

# --- Per-rep outbound volume + new accounts (HubSpot) -------------------
OWNER_ID_TO_REP = {
    "0000000": "{{AE_4}}", "0000000": "{{SDR_1}}",
    "0000000": "{{AE_6}}", "0000000": "Jason Polanco",
}

# Contacts created in last 7d grouped by owner (proxy for per-rep outbound volume)
contacts_7d = hs_post('/crm/v3/objects/contacts/search', {
    "filterGroups": [{"filters": [{"propertyName": "createdate", "operator": "GTE", "value": seven_days_iso}]}],
    "properties": ["createdate", "hubspot_owner_id"], "limit": 100
})
per_rep_contacts = defaultdict(int)
if isinstance(contacts_7d, dict):
    for c in contacts_7d.get('results', []):
        oid = c.get('properties', {}).get('hubspot_owner_id')
        rep = OWNER_ID_TO_REP.get(str(oid))
        if rep:
            per_rep_contacts[rep] += 1

# New companies created in last 7d (net-new accounts entering pipeline)
companies_7d = hs_post('/crm/v3/objects/companies/search', {
    "filterGroups": [{"filters": [{"propertyName": "createdate", "operator": "GTE", "value": seven_days_iso}]}],
    "properties": ["createdate"], "limit": 1
})
new_accounts_7d = companies_7d.get('total', 0) if isinstance(companies_7d, dict) else 0

# --- Calendar Meeting Counts (PRIMARY source) --------------------------
COMPANY_DOMAINS = ('@example.com', '@product.ai', '@example-org.com')

REPS = {
    "rep@example.com":   "{{AE_4}}",
    "rep@example.com": "{{SDR_1}}",
    "rep@example.com":   "{{AE_6}}",
    "rep@example.com":  "Jason Polanco",
}

tmin = (now - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
tmax = now.strftime('%Y-%m-%dT%H:%M:%SZ')

EXCLUDE_PATTERNS = ['standup', 'busy', 'hold', 'personal', 'lunch', 'dinner',
                    'catch up', '1:1', 'internal sync', 'prep', 'pre call',
                    'check in', '30-min meeting'] + [
                    p.strip().lower() for p in os.environ.get('MEETING_EXCLUDE_PATTERNS', '').split(',') if p.strip()]
EXPANSION_HINTS  = ['check in', 'upgrade', 'onboarding', 'renewal', 'follow up', 'kickoff',
                     'deep dive', 'deployment sync']

def classify_title(title):
    t = (title or '').lower()
    is_excluded = any(p in t for p in EXCLUDE_PATTERNS)
    is_expansion = any(p in t for p in EXPANSION_HINTS)
    return is_excluded, is_expansion

def get_external_attendees(event):
    atts = event.get('attendees', [])
    external = []
    for a in atts:
        email = (a.get('email') or '').lower()
        if email and not any(d in email for d in COMPANY_DOMAINS):
            external.append(email)
    return sorted(external)

counts_calendar_ok = defaultdict(bool)
calendar_failures = []
all_meetings = []
cancelled_total = 0

for cal, rep in REPS.items():
    events = gwsg_calendar_events(cal, tmin, tmax)
    if not events:
        calendar_failures.append(rep)
        continue
    counts_calendar_ok[rep] = True
    for e in events:
        if e.get('status') == 'cancelled':
            # Count cancellations of external meetings (dedup later)
            title = e.get('summary', '').strip()
            ext = get_external_attendees(e)
            if title and ext:
                is_excluded, _ = classify_title(title)
                if not is_excluded:
                    cancelled_total += 1
            continue
        title = e.get('summary', '').strip()
        if not title:
            continue
        ext = get_external_attendees(e)
        if not ext:
            continue
        is_excluded, is_expansion = classify_title(title)
        if is_excluded:
            continue

        org_email = ''
        org = e.get('organizer', {})
        if org:
            org_email = org.get('email', '').lower()
        if not org_email:
            org_email = e.get('creator', {}).get('email', '').lower()
        if not org_email:
            for a in e.get('attendees', []):
                em = (a.get('email') or '').lower()
                if any(d in em for d in COMPANY_DOMAINS):
                    org_email = em
                    break

        if org_email and any(d in org_email for d in COMPANY_DOMAINS):
            owner = REPS.get(org_email, rep)
        else:
            owner = rep

        all_meetings.append({
            'owner': owner, 'title': title, 'ext': ext, 'is_expansion': is_expansion,
            'start': e.get('start', {}).get('dateTime', ''),
        })

# Deduplicate: same title + same external attendees = same meeting
seen = set()
counts_netnew = defaultdict(int)
counts_expansion = defaultdict(int)
detail_exp = defaultdict(list)
meeting_companies = defaultdict(set)  # owner -> set of company domains
booked_total = 0

for m in all_meetings:
    dk = (m['title'], tuple(m['ext'][:3]))
    if dk in seen:
        continue
    seen.add(dk)
    booked_total += 1
    # Extract company domains from external attendees
    for em in m['ext']:
        if '@' in em:
            meeting_companies[m['owner']].add(em.split('@')[1])
    if m['is_expansion']:
        counts_expansion[m['owner']] += 1
        detail_exp[m['owner']].append(m['title'])
    else:
        counts_netnew[m['owner']] += 1

# --- HubSpot fallback for calendar failures ----------------------------
if calendar_failures:
    OWNER_MAP = {
        "0000000": "{{AE_4}}", "0000000": "{{SDR_1}}",
        "0000000": "{{AE_6}}", "0000000": "Jason Polanco",
    }
    hs_exclude = ['sync', 'check in', 'follow up', 'catch up', 'office hours',
                  'bi-weekly', 'next steps', 'hold:', 'governance']
    meetings_data = hs_post('/crm/v3/objects/meetings/search', {
        "filterGroups": [{"filters": [
            {"propertyName": "hs_meeting_start_time", "operator": "GTE", "value": seven_days_iso},
            {"propertyName": "hs_meeting_start_time", "operator": "LTE", "value": now.isoformat()}
        ]}],
        "properties": ["hs_meeting_start_time", "hubspot_owner_id", "hs_meeting_title"],
        "limit": 100
    })
    for m in meetings_data.get('results', []):
        props = m.get('properties', {})
        oid = str(props.get('hubspot_owner_id', ''))
        rep = OWNER_MAP.get(oid)
        if rep not in calendar_failures:
            continue
        title = props.get('hs_meeting_title', '')
        is_excluded, is_expansion = classify_title(title)
        if is_excluded:
            continue
        if is_expansion:
            counts_expansion[rep] += 1
        else:
            counts_netnew[rep] += 1

# --- Company metrics for meeting companies (HubSpot) --------------------
def lookup_company(domain):
    """Look up a company by domain in HubSpot, return key metrics."""
    r = hs_post('/crm/v3/objects/companies/search', {
        "filterGroups": [{"filters": [{"propertyName": "domain", "operator": "EQ", "value": domain}]}],
        "properties": ['name', 'domain', 'annualrevenue', 'numberofemployees', 'industry',
                       'number_of_icp_contacts', 'hs_lead_status'],
        "limit": 1
    })
    if isinstance(r, dict) and r.get('results'):
        p = r['results'][0].get('properties', {})
        return {
            'name': p.get('name', domain),
            'revenue': p.get('annualrevenue'),
            'employees': p.get('numberofemployees'),
            'industry': p.get('industry'),
            'icp_contacts': p.get('number_of_icp_contacts'),
        }
    return None

def fmt_money(v):
    if not v:
        return 'n/a'
    try:
        v = float(v)
        if v >= 1e9:
            return f'${v/1e9:.1f}B'
        if v >= 1e6:
            return f'${v/1e6:.0f}M'
        return f'${v/1e3:.0f}K'
    except Exception:
        return str(v)

def fmt_emp(v):
    if not v:
        return 'n/a'
    try:
        return f'{int(float(v)):,}'
    except Exception:
        return str(v)

def icp_fit(cm):
    """Classify company as Enterprise or Mid Market based on ICP floor (1,000+ emp, $250M+ rev)."""
    emp = cm.get('employees')
    rev = cm.get('revenue')
    try:
        if emp and float(emp) >= 1000:
            return 'Enterprise'
        if rev and float(rev) >= 250e6:
            return 'Enterprise'
    except Exception:
        pass
    return 'Mid Market'

# Enrich each rep's meeting companies
company_metrics = {}  # domain -> metrics
for owner, domains in meeting_companies.items():
    for d in domains:
        if d in company_metrics:
            continue
        company_metrics[d] = lookup_company(d)
        time.sleep(0.1)

# --- Aircall: per-rep call activity (rolling 7d) -------------------------
AC_ID = env('AIRCALL_API_ID')
AC_TOK = env('AIRCALL_API_TOKEN') or env('AIRCALL_API_KEY')

def aircall_get(path):
    auth = base64.b64encode(f'{AC_ID}:{AC_TOK}'.encode()).decode()
    req = urllib.request.Request(
        f'https://api.aircall.io/v1{path}',
        headers={'Authorization': f'Basic {auth}', 'User-Agent': 'Mozilla/5.0'}
    )
    return json.loads(urllib.request.urlopen(req, timeout=60).read())

ac_rep_stats = defaultdict(lambda: {'dials': 0, 'connects': 0, 'short': 0, 'talk_sec': 0})
ac_total_dials = 0
ac_total_connects = 0
ac_total_short = 0
AC_CONNECT_MIN_SEC = 30  # under 30s = voicemail/brush-off, not a real connect
ac_error = None

if AC_ID and AC_TOK:
    try:
        seven_days_ts = int((now - timedelta(days=7)).timestamp())
        page = 1
        fetched = 0
        total_calls = None
        while True:
            batch = aircall_get(f'/calls?per_page=50&order=desc&from={seven_days_ts}&page={page}')
            call_list = batch.get('calls', [])
            meta = batch.get('meta', {})
            if total_calls is None:
                total_calls = meta.get('total', 0)
            for c in call_list:
                if c.get('direction') != 'outbound':
                    continue
                user = (c.get('user') or {}).get('name', 'Unknown')
                st = ac_rep_stats[user]
                st['dials'] += 1
                ac_total_dials += 1
                if c.get('answered_at'):
                    dur = int(c.get('duration') or 0)
                    if dur >= AC_CONNECT_MIN_SEC:
                        st['connects'] += 1
                        ac_total_connects += 1
                        st['talk_sec'] += dur
                    else:
                        st['short'] += 1
                        ac_total_short += 1
            fetched += len(call_list)
            if fetched >= (total_calls or 0) or not call_list:
                break
            page += 1
            time.sleep(0.2)
    except Exception as e:
        ac_error = str(e)
else:
    ac_error = 'missing Aircall creds'

# --- HubSpot Sequences ------------------------------------------------
seq_contacts = hs_post('/crm/v3/objects/contacts/search', {
    "filterGroups": [{"filters": [{"propertyName": "hs_sequences_is_enrolled", "operator": "EQ", "value": "true"}]}],
    "properties": ["hs_sequences_is_enrolled"], "limit": 1
})
active_seq = seq_contacts.get('total', 0) if isinstance(seq_contacts, dict) else 0

# --- Events (Black Hat / AI4) ------------------------------------------
EVENTS_SHEET = "REDACTED_GOOGLE_ID"
master = gwsg_json(EVENTS_SHEET, "A1:I200")
vals = master.get('values', [])
event_counts = Counter()
event_by_rep = defaultdict(Counter)
if vals:
    hdr = vals[0]
    ev_idx = hdr.index('Event') if 'Event' in hdr else 0
    rep_idx = hdr.index('Assigned Rep') if 'Assigned Rep' in hdr else None
    for row in vals[1:]:
        if len(row) > ev_idx and row[ev_idx].strip():
            ev = row[ev_idx].strip()
            event_counts[ev] += 1
            if rep_idx is not None and len(row) > rep_idx and row[rep_idx].strip():
                event_by_rep[ev][row[rep_idx].strip()] += 1

# Follow-up leads (badge scans)
bh_leads = gwsg_json("REDACTED_GOOGLE_ID", "A1:Z300")
vals2 = bh_leads.get('values', [])
temps = Counter()
if vals2:
    hdr2 = vals2[0]
    temp_idx = hdr2.index('Temperature') if 'Temperature' in hdr2 else None
    for row in vals2[1:]:
        if temp_idx is not None and len(row) > temp_idx and row[temp_idx].strip():
            temps[row[temp_idx].strip()] += 1

# Tracker
tracker = gwsg_json("REDACTED_GOOGLE_ID", "A1:G60")
vals3 = tracker.get('values', [])
tracker_line = "No tracker data"
# Team-wide cadence line (completion %, overdue) always captured
for row in vals3:
    if any('%' in str(c) or 'completion' in str(c).lower() for c in row):
        tracker_line = ' | '.join(row)
        break
# REP SUMMARY block reflects actual follow-up work (attempted to contact, connected),
# which is more accurate than task-completion % (reps email but don't always close tasks).
bh_rep_rows = []
for i, row in enumerate(vals3):
    if row and row[0].strip().upper() == 'REP SUMMARY':
        for r in vals3[i+2:]:
            if not r or not r[0].strip():
                continue
            if r[0].strip().upper() == 'TOTAL':
                continue
            if r[0].strip().upper() in ('STATUS KEY', 'FLAGGED'):
                break
            bh_rep_rows.append({
                'rep': r[0].strip(),
                'total': r[1].strip() if len(r) > 1 else '0',
                'attempted': r[2].strip() if len(r) > 2 else '0',
                'connected': r[3].strip() if len(r) > 3 else '0',
                'open_deal': r[4].strip() if len(r) > 4 else '0',
            })
        break

# --- Build report ------------------------------------------------------
REP_ORDER = ["{{AE_4}}", "{{SDR_1}}", "{{AE_6}}", "Jason Polanco"]
total_new = sum(counts_netnew.values())
total_exp = sum(counts_expansion.values())

# --- Live TLDR + suggestions -------------------------------------------
tldr_parts = []
suggestions = []

# WoW trends
sent_arrow, sent_pct = wow_trend('total_sent', total_sent)
meet_arrow, meet_pct = wow_trend('total_new', total_new)
clay_arrow, clay_pct = wow_trend('clay_enriched_7d', clay_enriched_7d)

# Outbound
tldr_parts.append(f"{total_sent:,} emails sent {arrow_sym(sent_arrow)}")
if reply_rate < 0.3:
    suggestions.append(f"Reply rate is low ({reply_rate}%). Review subject lines and openers on the top campaigns.")
elif reply_rate < 0.5:
    suggestions.append(f"Reply rate at {reply_rate}% - consider refreshing copy on underperforming sequences.")

# Meetings
tldr_parts.append(f"{total_new} net-new meetings {arrow_sym(meet_arrow)}, {total_exp} expansion")
low_reps = [r for r in REP_ORDER if counts_netnew.get(r, 0) == 0]
if low_reps:
    suggestions.append(f"{', '.join(low_reps)} had 0 net-new meetings this week - check pipeline coverage.")
if total_exp > 0:
    suggestions.append(f"{total_exp} expansion meetings - prioritize these for upsell/renewal.")

# Booked vs cancelled
if booked_total:
    cancel_pct = round((cancelled_total / (booked_total + cancelled_total)) * 100) if (booked_total + cancelled_total) else 0
    tldr_parts.append(f"{booked_total} booked, {cancelled_total} cancelled")
    if cancel_pct > 15:
        suggestions.append(f"{cancel_pct}% of booked meetings cancelled ({cancelled_total}) - check scheduling quality.")

# Clay
tldr_parts.append(f"{clay_enriched_7d} leads enriched (7d) {arrow_sym(clay_arrow)}")
if clay_enriched_7d < 50:
    suggestions.append(f"Clay enrichment volume is low ({clay_enriched_7d}/7d). Check dispatch pipeline.")

# New accounts
if new_accounts_7d:
    tldr_parts.append(f"{new_accounts_7d} new accounts")

# Events
bh_dinner = event_counts.get('Black Hat Executive Dinner', 0)
ai4_dinner = event_counts.get('AI4 Executive Dinner', 0)
if bh_dinner or ai4_dinner:
    tldr_parts.append(f"{bh_dinner} Black Hat + {ai4_dinner} AI4 dinner contacts")
    if temps:
        tldr_parts.append(f"{sum(temps.values())} badge scans ({temps.get('Hot',0)} Hot)")

# Tracker overdue
if 'overdue' in tracker_line.lower():
    import re
    m = re.search(r'(\d+)\s+tasks overdue', tracker_line)
    if m:
        overdue = int(m.group(1))
        if overdue > 0:
            suggestions.append(f"{overdue} follow-up tasks overdue on the Black Hat cadence - clear these first.")

tldr = ' | '.join(tldr_parts)

# Persist today's numbers for WoW comparison
save_history({
    'total_sent': total_sent,
    'total_new': total_new,
    'clay_enriched_7d': clay_enriched_7d,
    'date': now.strftime('%Y-%m-%d'),
})

lines = []
lines.append(":zap: *TLDR*")
lines.append(tldr)
lines.append("")

lines.append(":e-mail: *Outbound (Smartlead, cumulative)*")
lines.append(f"Emails sent: {total_sent:,} {arrow_sym(sent_arrow)}{f' ({sent_pct:+.1f}% WoW)' if sent_pct is not None else ''}")
lines.append(f"Replies: {total_replies} ({reply_rate}%)")
lines.append(f"Bounces: {total_bounces} ({bounce_rate}%)")
lines.append(f"Active campaigns: {active_camps}")
lines.append("")

lines.append(":sparkles: *Clay Enrichment (rolling 7d)*")
lines.append(f"Leads enriched: {clay_enriched_7d:,} {arrow_sym(clay_arrow)}{f' ({clay_pct:+.1f}% WoW)' if clay_pct is not None else ''}")
lines.append("")

lines.append(":calendar: *New Customer Meetings (Last 7d)*")
for rep in REP_ORDER:
    nn = counts_netnew.get(rep, 0)
    exp = counts_expansion.get(rep, 0)
    src = "[CAL]" if counts_calendar_ok.get(rep) else "[HS]"
    if nn or exp:
        lines.append(f"  {src} {rep}: {nn} new ({exp} expansion)")
    else:
        lines.append(f"  {src} {rep}: 0")
lines.append(f"  Team total: {total_new} new {arrow_sym(meet_arrow)}{f' ({meet_pct:+.1f}% WoW)' if meet_pct is not None else ''}, {total_exp} expansion")
lines.append(f"  Booked vs cancelled: {booked_total} booked, {cancelled_total} cancelled")
if calendar_failures:
    lines.append(f"  (Fallback used for: {', '.join(calendar_failures)})")
lines.append("")

lines.append(":bust_in_silhouette: *Per-Rep Outbound Volume (7d)*")
for rep in REP_ORDER:
    lines.append(f"  {rep}: {per_rep_contacts.get(rep, 0)} contacts added")
lines.append(f"  New accounts added: {new_accounts_7d}")
lines.append("")

lines.append(":arrow_upper_right: *Customer Expansion Meetings*")
has_exp = False
for rep in REP_ORDER:
    exp = counts_expansion.get(rep, 0)
    if exp:
        has_exp = True
        dets = detail_exp.get(rep, [])
        if dets:
            lines.append(f"  {rep}: {exp} - {dets[0][:50]}{'...' if len(dets[0]) > 50 else ''}")
        else:
            lines.append(f"  {rep}: {exp}")
if not has_exp:
    lines.append("  None this week")
lines.append("")

lines.append(":office: *Meeting Company Profiles*")
shown_any = False
for rep in REP_ORDER:
    domains = meeting_companies.get(rep, set())
    if not domains:
        continue
    lines.append(f"  *{rep}*")
    for d in sorted(domains):
        cm = company_metrics.get(d)
        if cm:
            shown_any = True
            lines.append(f"    {cm['name']} ({icp_fit(cm)})")
        else:
            shown_any = True
            lines.append(f"    {d} (not in HubSpot)")
if not shown_any:
    lines.append("  No company data available")
lines.append("")

lines.append(":telephone_receiver: *BDR Call Activity (Aircall, rolling 7d)*")
if ac_error:
    lines.append(f"  ⚠️ Aircall fetch failed: {ac_error}")
elif ac_total_dials == 0:
    lines.append("  No outbound calls logged in the last 7 days")
else:
    AC_REP_ORDER = ["{{AE_2}}", "{{AE_5}}", "Jason Polanco"]
    for rep in AC_REP_ORDER:
        st = ac_rep_stats.get(rep)
        if not st or st['dials'] == 0:
            lines.append(f"  {rep}: 0 dials")
            continue
        conn_rate = round((st['connects'] / st['dials']) * 100, 1)
        talk_min = round(st['talk_sec'] / 60, 1)
        lines.append(f"  {rep}: {st['dials']} dials, {st['connects']} connects ({conn_rate}%), {st['short']} short/VM, {talk_min} min talk")
    # any other users not in the known order
    for rep, st in ac_rep_stats.items():
        if rep not in AC_REP_ORDER and st['dials'] > 0:
            conn_rate = round((st['connects'] / st['dials']) * 100, 1)
            lines.append(f"  {rep}: {st['dials']} dials, {st['connects']} connects ({conn_rate}%), {st['short']} short/VM")
    team_conn_rate = round((ac_total_connects / ac_total_dials) * 100, 1)
    lines.append(f"  Team total: {ac_total_dials} dials, {ac_total_connects} connects ({team_conn_rate}%), {ac_total_short} short/VM")
    lines.append(f"  (connect = 30s+ talk; short/VM = answered under 30s)")
lines.append("")

lines.append(":repeat: *Sequences*")
lines.append(f"  Active contacts in sequences: {active_seq:,}")
lines.append("")

lines.append(":tophat: *Black Hat Follow-Up*")
if bh_rep_rows:
    for r in bh_rep_rows:
        lines.append(f"  {r['rep']}: {r['attempted']}/{r['total']} contacted, {r['connected']} connected")
    lines.append(f"  {tracker_line}")
else:
    lines.append(f"  {tracker_line}")
lines.append("")

lines.append(":tophat: *Events*")
for ev, cnt in event_counts.most_common():
    lines.append(f"  {ev}: {cnt} attendees")
if temps:
    lines.append(f"  Badge scans: {sum(temps.values())} total ({temps.get('Hot',0)} Hot, {temps.get('Warm',0)} Warm)")
lines.append("")

lines.append(":bulb: *Suggested Focus*")
if suggestions:
    for s in suggestions:
        lines.append(f"  - {s}")
else:
    lines.append("  - Machine is running well. Keep volume up and follow through on expansion meetings.")

print('\n'.join(lines))
