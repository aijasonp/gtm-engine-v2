#!/usr/bin/env python3
import json, os, time, urllib.request

API = "https://api.floqer.com/api/v1"
WF = "00000000-0000-0000-0000-000000000000"
KEY = os.environ["FLOQER_API_KEY"]

def api(path, body):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), method="POST")
    req.add_header("Authorization", f"Bearer {KEY}")
    req.add_header("Content-Type", "application/json")
    return json.loads(urllib.request.urlopen(req).read())

def list_all():
    rows = []
    page = 1
    while True:
        d = api(f"/workflows/{WF}/sheets/{WF}/rows/list", {"page_size": 200, "page_no": page})
        rws = d.get("data", {}).get("rows", [])
        rows += rws
        if len(rws) < 200:
            break
        page += 1
    return rows

rows = list_all()
from collections import Counter
print("statuses:", dict(Counter(r.get("row_status") for r in rows)))

# target = pending or failed rows (retry)
target = [r["row_id"] for r in rows if r.get("row_status") in ("pending", "has_failures")]
print("target rows:", len(target))
json.dump(target, open("/tmp/retry_ids.json", "w"))

if target:
    print("run:", json.dumps(api(f"/workflows/{WF}/sheets/{WF}/run", {"row_ids": target}))[:300])
    tset = set(target)
    for i in range(60):
        time.sleep(10)
        rows = list_all()
        mine = [r for r in rows if r.get("row_id") in tset]
        st = {r.get("row_status") for r in mine}
        print(f"  poll {i}: {len(mine)}/{len(tset)} statuses={st}")
        if st and st <= {"complete", "has_failures"} and len(mine) >= len(tset):
            json.dump(mine, open("/tmp/gtm_agent_results.json", "w"))
            print("DONE")
            break
    else:
        print("TIMEOUT")
