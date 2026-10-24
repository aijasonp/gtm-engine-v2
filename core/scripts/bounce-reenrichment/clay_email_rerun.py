#!/usr/bin/env python3
"""Re-post to Clay cadence waterfall with EMPTY email so the email waterfall fires.

First pass put the bounced email in the payload -> 'Need email?' gated out the email
providers entirely (only mobiles ran). Empty email forces the email branch.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CLAY = os.path.expanduser("~/.local/bin/clay-bin")
WEBHOOK = "https://api.clay.com/v3/sources/webhook/00000000-0000-0000-0000-000000000000"
WF = "wf_0tm4s54NmUS3okFGU9e"

rows = json.load(open(os.path.join(HERE, "final_rows.json")))
# All 8 rows that went through Clay first pass and got email=clay_miss_same_or_none
misses = [r for r in rows if r.get("final_email_source") == "clay_miss_same_or_none"]
print(f"re-posting {len(misses)} rows with empty email", flush=True)

def post(r):
    parts = r["full_name"].split(" ", 1)
    payload = {
        "row": str(r["row"]),
        "email": "",  # EMPTY so Need email? -> run email waterfall
        "full_name": r["full_name"],
        "first_name": parts[0],
        "last_name": parts[1] if len(parts) > 1 else "",
        "company_name": r["company"],
        "company_domain": r["domain"],
        "job_title": r["title"],
        "linkedin_url": r["linkedin"] or ("https://www.linkedin.com/in/dave-yoken" if r["row"] == 2 else ""),
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(WEBHOOK, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]

start_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
ok = err = 0
for r in misses:
    st, body = post(r)
    if 200 <= st < 300:
        ok += 1
        print(f"  row {r['row']} {r['full_name']}: POST {st}", flush=True)
    else:
        err += 1
        print(f"  row {r['row']} {r['full_name']}: FAIL {st} {body}", flush=True)
    time.sleep(0.5)
print(f"posted ok={ok} err={err}", flush=True)

def list_runs(after_iso):
    runs, cursor = [], None
    while True:
        cmd = [CLAY, "workflows", "runs", "list", WF,
               "--created-after", after_iso, "--limit", "100"]
        if cursor:
            cmd += ["--cursor", cursor]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        try:
            d = json.loads(out.stdout)
        except Exception:
            break
        runs += d.get("data", [])
        cursor = d.get("cursor")
        if not cursor:
            break
    return runs

runs = []
for _ in range(60):
    time.sleep(25)
    runs = list_runs(start_iso)
    done = [x for x in runs if x.get("status") == "completed"]
    active = [x for x in runs if x.get("status") in ("running", "pending")]
    print(f"[wait] total={len(runs)} completed={len(done)} active={len(active)}", flush=True)
    if len(runs) >= len(misses) and not active:
        break

def harvest(rid):
    out = subprocess.run([CLAY, "workflows", "runs", "steps", WF, rid],
                         capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        return None
    try:
        d = json.loads(out.stdout)
    except Exception:
        return None
    row_id, email_out, email_prov = "", "", ""
    for s in d.get("data", []):
        nm = s.get("nodeName") or ""
        o = s.get("stepOutputs") or {}
        if nm == "Webhook":
            row_id = str(o.get("row") or "").strip()
        res = o.get("result")
        if nm.startswith("LeadMagic email") and isinstance(res, dict) and not email_out:
            em = res.get("email") or (res.get("data") or {}).get("email") if isinstance(res.get("data"), dict) else res.get("email")
            if em:
                email_out, email_prov = em, "leadmagic"
        elif nm.startswith("Findymail email") and isinstance(res, dict) and not email_out:
            em = res.get("email")
            if not em and isinstance(res.get("data"), dict):
                em = res["data"].get("email")
            if em:
                email_out, email_prov = em, "findymail"
        elif nm.startswith("Datagma email") and isinstance(res, dict) and not email_out:
            em = res.get("email")
            if not em and isinstance(res.get("data"), dict):
                em = res["data"].get("email")
            if em:
                email_out, email_prov = em, "datagma"
    return {"row": row_id, "email": email_out, "email_provider": email_prov}

results = {}
for x in runs:
    if x.get("status") != "completed":
        continue
    rec = harvest(x["runId"])
    if rec and rec["row"]:
        results[rec["row"]] = rec
        print(f"  row {rec['row']}: email={rec['email'] or '-'} ({rec['email_provider'] or '-'})", flush=True)

# merge
for r in rows:
    if r.get("final_email"):
        continue
    hit = results.get(str(r["row"]))
    if hit and hit["email"] and hit["email"].lower() != r["bounced_email"].lower():
        r["final_email"] = hit["email"].lower()
        r["final_email_source"] = f"clay_email:{hit['email_provider']}"

json.dump(rows, open(os.path.join(HERE, "final_rows.json"), "w"), indent=2)
found = sum(1 for r in rows if r.get("final_email"))
print(f"\nFINAL emails: {found}/{len(rows)}", flush=True)
for r in rows:
    print(f"  row {r['row']:>2} {r['full_name']:<22} email={r.get('final_email') or '-':<35} src={r.get('final_email_source') or '-'}", flush=True)
