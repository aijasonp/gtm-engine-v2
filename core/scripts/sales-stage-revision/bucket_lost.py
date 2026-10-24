#!/usr/bin/env python3
import requests, os, collections
from pathlib import Path

env = {}
for line in Path(os.path.expanduser("~/.openclaw/.env")).read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
tok = env.get("HUBSPOT_TOKEN")
if not tok:
    raise SystemExit("no HUBSPOT_TOKEN")

h = {"Authorization": f"Bearer {tok}"}
url = "https://api.hubapi.com/crm/v3/objects/deals/search"
body = {"filterGroups":[{"filters":[{"propertyName":"closed_lost_reason","operator":"HAS_PROPERTY"}]}],
        "properties":["closed_lost_reason","dealname","closedate"],"limit":100}
reasons=[]
after=None
while True:
    if after: body["after"]=after
    r=requests.post(url,headers=h,json=body,timeout=30); r.raise_for_status(); d=r.json()
    for res in d.get("results",[]):
        v=(res.get("properties",{}).get("closed_lost_reason") or "").strip()
        if v: reasons.append(v)
    if d.get("paging",{}).get("next",{}).get("after"): after=d["paging"]["next"]["after"]
    else: break

def bucket(r):
    rl=r.lower()
    if 'interest logged' in rl or 'not in pipeline' in rl or 'not a real deal' in rl:
        return 'Pipeline hygiene / not a real deal (Interest Logged, no progress)'
    if 'no budget' in rl or ('budget' in rl and ('no ' in rl or 'lack' in rl or 'unwilling' in rl)):
        return 'No budget / lack of budget'
    if any(x in rl for x in ['out of country','not icp','not a target','not a good fit','not a fit','small org','not a good icp']):
        return 'Not ICP / not a target account'
    if any(x in rl for x in ['no response','gone dark','no show','unresponsive','no reply','no coms','no interaction','no activity','no movement','no engagement','ghost','stagnat','no traction','no momentum','no real shot','not ready','not a priority','not interested','no appetite','no willingness','no momentum']):
        return 'No response / no engagement / went dark'
    if 'duplicate' in rl or 'dup' in rl:
        return 'Duplicate deal / account'
    if any(x in rl for x in ['competitor','chose','went with','selected','msft','microsoft','another vendor','other vendor','built their own','build it themselves','in-house','in house','langchain','lang chain','n8n','openai','bedrock','glean','amazon quick']):
        return 'Lost to competitor / alternative (incl. build in-house)'
    if any(x in rl for x in ['left the company','left company','sponsor left','moved on','left to','left and','person has left','has left']):
        return 'Champion / sponsor left or moved on'
    if any(x in rl for x in ['not a real company','not a real opportunity','not a real inquiry','not a real lead','bad data','not a valid email','no company attached','not sure what this deal','not sure what this is','do not know what this is','weird lead','fake']):
        return 'Bad data / not a real opportunity'
    if any(x in rl for x in ['timing','not ready','later','next year','2027','mid 2026','early 2026','not a good time','not the right time','too early']):
        return 'Timing / not ready yet'
    if 'partner' in rl and any(x in rl for x in ['not interested','not looking','resell','reseller','not an end user','not a purchase']):
        return 'Partner / reseller not purchasing'
    if any(x in rl for x in ['no authority','no pull','no champion','no clear champion']):
        return 'No authority / no champion'
    if any(x in rl for x in ['product','misalign','requirement','coverage','integration','can\'t validate','doesn\'t work','not working','technical']):
        return 'Product / technical gap'
    if any(x in rl for x in ['moved into another','moved to another','another opportunity','rolled into','part of the angles']):
        return 'Consolidated into another opportunity'
    if any(x in rl for x in ['discontinue','divestiture','going to rfp','rfp','reorg','downsizing','layoff']):
        return 'Company change (RFP, divestiture, reorg)'
    if any(x in rl for x in ['not moving forward','decided against','decided not to','not going to','not moving','not willing','not applicable','no opportunity','no real appetitie']):
        return 'Decided not to move forward / no need now'
    return 'Other / one-off'

cats=collections.Counter()
for r in reasons: cats[bucket(r)]+=1
print("TOTAL:", len(reasons))
print()
for c,n in cats.most_common():
    print(f"{n:4d}  {c}")
