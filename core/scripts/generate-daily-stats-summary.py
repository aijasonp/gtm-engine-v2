#!/usr/bin/env python3
"""Daily stats summary for #gtm-bizdev (SLACK_ID).

Compact daily snapshot: Smartlead sends/replies/bounces (cumulative + WoW),
Clay enrichment (7d), new accounts (7d), active sequences, per-rep outbound
volume (7d). Prints Slack mrkdwn to stdout; the cron agentTurn delivers it
verbatim to the channel.
"""
import json, os, urllib.request, time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

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

now = datetime.now(timezone.utc)
seven_days_iso = (now - timedelta(days=7)).isoformat()

# --- Smartlead --------------------------------------------------------
SL_BASE = 'https://server.smartlead.ai/api/v1'
sl_key = env('SMARTLEAD_API_KEY')
SL_AUTH = '?api' + '_key=' + sl_key

camps = http_get(SL_BASE + '/campaigns' + SL_AUTH)
if isinstance(camps, dict) and camps.get('_error'):
    camps = []
camp_list = camps if isinstance(camps, list) else camps.get('data', []) if isinstance(camps, dict) else []

active_camps = 0
total_sent = total_replies = total_bounces = 0
for c in camp_list:
    cid = str(c.get('id', ''))
    if c.get('status') in ('ACTIVE', 'RUNNING'):
        active_camps += 1
    stats = http_get(SL_BASE + '/campaigns/' + cid + '/analytics' + SL_AUTH)
    if isinstance(stats, dict) and '_error' not in stats:
        total_sent += int(stats.get('sent_count', 0) or 0)
        total_replies += int(stats.get('reply_count', 0) or 0)
        total_bounces += int(stats.get('bounce_count', 0) or 0)
    time.sleep(0.15)

reply_rate = round((total_replies / total_sent) * 100, 2) if total_sent else 0
bounce_rate = round((total_bounces / total_sent) * 100, 2) if total_sent else 0

# --- WoW history ------------------------------------------------------
HIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gtm-history.json')
def load_history():
    try:
        with open(HIST_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def wow(key, current):
    prev = load_history().get(key)
    if prev is None or prev == 0:
        return ''
    pct = round(((current - prev) / prev) * 100, 1)
    sym = ':arrow_up:' if pct > 2 else (':arrow_down:' if pct < -2 else ':arrow_right:')
    return f' {sym} ({pct:+.1f}% WoW)'

# --- Clay enrichment (7d) via HubSpot contacts created ----------------
clay = hs_post('/crm/v3/objects/contacts/search', {
    "filterGroups": [{"filters": [{"propertyName": "createdate", "operator": "GTE", "value": seven_days_iso}]}],
    "properties": ["createdate"], "limit": 1
})
clay_enriched_7d = clay.get('total', 0) if isinstance(clay, dict) else 0

# --- New accounts (7d) ------------------------------------------------
comp = hs_post('/crm/v3/objects/companies/search', {
    "filterGroups": [{"filters": [{"propertyName": "createdate", "operator": "GTE", "value": seven_days_iso}]}],
    "properties": ["createdate"], "limit": 1
})
new_accounts_7d = comp.get('total', 0) if isinstance(comp, dict) else 0

# --- Active sequences -------------------------------------------------
seq = hs_post('/crm/v3/objects/contacts/search', {
    "filterGroups": [{"filters": [{"propertyName": "hs_sequences_is_enrolled", "operator": "EQ", "value": "true"}]}],
    "properties": ["hs_sequences_is_enrolled"], "limit": 1
})
active_seq = seq.get('total', 0) if isinstance(seq, dict) else 0

# --- Per-rep outbound volume (7d) -------------------------------------
OWNER_ID_TO_REP = {
    "0000000": "{{AE_4}}", "0000000": "{{SDR_1}}",
    "0000000": "{{AE_6}}", "0000000": "Jason Polanco",
}
contacts_7d = hs_post('/crm/v3/objects/contacts/search', {
    "filterGroups": [{"filters": [{"propertyName": "createdate", "operator": "GTE", "value": seven_days_iso}]}],
    "properties": ["createdate", "hubspot_owner_id"], "limit": 100
})
per_rep = defaultdict(int)
if isinstance(contacts_7d, dict):
    for c in contacts_7d.get('results', []):
        rep = OWNER_ID_TO_REP.get(str(c.get('properties', {}).get('hubspot_owner_id')))
        if rep:
            per_rep[rep] += 1

# --- Build -------------------------------------------------------------
REP_ORDER = ["{{AE_4}}", "{{SDR_1}}", "{{AE_6}}", "Jason Polanco"]
date_str = now.strftime('%Y-%m-%d')

lines = []
lines.append(f":bar_chart: *Daily Stats Summary — {date_str}*")
lines.append("")
lines.append(":e-mail: *Outbound (Smartlead, cumulative)*")
lines.append(f"  Emails sent: {total_sent:,}{wow('total_sent', total_sent)}")
lines.append(f"  Replies: {total_replies} ({reply_rate}%)")
lines.append(f"  Bounces: {total_bounces} ({bounce_rate}%)")
lines.append(f"  Active campaigns: {active_camps}")
lines.append("")
lines.append(":sparkles: *Pipeline (rolling 7d)*")
lines.append(f"  Leads enriched (Clay): {clay_enriched_7d:,}{wow('clay_enriched_7d', clay_enriched_7d)}")
lines.append(f"  New accounts added: {new_accounts_7d}")
lines.append(f"  Active contacts in sequences: {active_seq:,}")
lines.append("")
lines.append(":bust_in_silhouette: *Per-Rep Outbound Volume (7d)*")
for rep in REP_ORDER:
    lines.append(f"  {rep}: {per_rep.get(rep, 0)} contacts added")

print('\n'.join(lines))
