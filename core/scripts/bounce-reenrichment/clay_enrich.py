#!/usr/bin/env python3
"""Post MoltSets misses to Clay cadence waterfall (wf_0tm4s54NmUS3okFGU9e).

The workflow has both email (LeadMagic 1cr -> Findymail 2cr -> Datagma 2cr) and
mobile (Lyne 4cr -> Wiza 7cr -> Findymail 9cr -> Prospeo 10cr -> BetterContact 30cr)
branches. Webhook trigger: 00000000-0000-0000-0000-000000000000.
Webhook URL: https://api.clay.com/v3/sources/webhook/00000000-0000-0000-0000-000000000000
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

rows = json.load(open(os.path.join(HERE, "moltsets_results.json")))
misses = [r for r in rows if r["ms_status"] != "ok"]

# The Cadence workflow HARD FAILS if linkedin_url is empty (learned AI Gov World 2026-10-16).
# Filter to rows with LinkedIn only. No-LinkedIn rows stay MoltSets-only and get flagged.
postable = [r for r in misses if r["linkedin"]]
no_linkedin = [r for r in misses if not r["linkedin"]]
print(f"misses: {len(misses)}; postable (has LinkedIn): {len(postable)}; SKIPPED no_linkedin: {len(no_linkedin)}", flush=True)
for r in no_linkedin:
    print(f"  SKIP_NO_LINKEDIN row {r['row']} {r['full_name']}", flush=True)
misses = postable

def post(r):
    parts = r["full_name"].split(" ", 1)
    payload = {
        "row": str(r["row"]),
        "email": r["bounced_email"].lower(),  # providers will treat as seed; bounced flag in notes
        "full_name": r["full_name"],
        "first_name": parts[0],
        "last_name": parts[1] if len(parts) > 1 else "",
        "company_name": r["company"],
        "company_domain": r["domain"],
        "job_title": r["title"],
        "linkedin_url": r["linkedin"] or "",
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(WEBHOOK, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]

start_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
print(f"posting {len(misses)} misses (start {start_iso})", flush=True)
ok = err = 0
for r in misses:
    st, body = post(r)
    if 200 <= st < 300:
        ok += 1
        print(f"  row {r['row']} {r['full_name']}: POST {st}", flush=True)
    else:
        err += 1
        print(f"  row {r['row']} {r['full_name']}: POST FAIL {st} {body}", flush=True)
    time.sleep(0.5)
print(f"posted ok={ok} err={err}", flush=True)

after = start_iso  # full ISO datetime required by --created-after
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
            print("  list_runs parse fail:", out.stdout[:300], out.stderr[:200], flush=True)
            break
        runs += d.get("data", [])
        cursor = d.get("cursor")
        if not cursor:
            break
    return runs

runs = []
for _ in range(60):  # up to ~30 min
    time.sleep(30)
    runs = list_runs(after)
    done = [x for x in runs if x.get("status") == "completed"]
    active = [x for x in runs if x.get("status") in ("running", "pending")]
    failed = [x for x in runs if x.get("status") == "failed"]
    print(f"[wait] total={len(runs)} completed={len(done)} active={len(active)} failed={len(failed)}", flush=True)
    if len(runs) >= len(misses) and not active:
        break

print(f"final runs: {len(runs)}", flush=True)
json.dump(runs, open(os.path.join(HERE, "clay_runs.json"), "w"), indent=2)

# ---- harvest results per run ----
def harvest(rid):
    out = subprocess.run([CLAY, "workflows", "runs", "steps", WF, rid],
                         capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        return None
    try:
        d = json.loads(out.stdout)
    except Exception:
        return None
    row_id, email_out, phone_out, email_prov, phone_prov = "", "", "", "", ""
    for s in d.get("data", []):
        nm = s.get("nodeName") or ""
        o = s.get("stepOutputs") or {}
        if nm == "Webhook":
            row_id = str(o.get("row") or "").strip()
        res = o.get("result")
        # email providers
        if nm.startswith("LeadMagic email") and isinstance(res, dict):
            em = res.get("email") or (res.get("data") or {}).get("email")
            if em and not email_out:
                email_out, email_prov = em, "leadmagic"
        elif nm.startswith("Findymail email") and isinstance(res, dict):
            em = res.get("email") or (res.get("data") or {}).get("email")
            if em and not email_out:
                email_out, email_prov = em, "findymail"
        elif nm.startswith("Datagma email") and isinstance(res, dict):
            em = res.get("email") or (res.get("data") or {}).get("email")
            if em and not email_out:
                email_out, email_prov = em, "datagma"
        # mobile providers
        if "Lyne" in nm and isinstance(res, dict) and res.get("mobile_phone") and not phone_out:
            phone_out, phone_prov = res["mobile_phone"], "lyne"
        elif "Wiza" in nm and isinstance(res, dict):
            data = res.get("data") or {}
            for p in (data.get("phones") or []) if isinstance(data, dict) else []:
                if isinstance(p, dict) and p.get("type") == "mobile" and p.get("number") and not phone_out:
                    phone_out, phone_prov = p["number"], "wiza"
                    break
        elif "Findymail mobile" in nm and isinstance(res, dict) and res.get("mobilePhone") and not phone_out:
            phone_out, phone_prov = res["mobilePhone"], "findymail"
        elif "Prospeo mobile" in nm and isinstance(res, dict) and not phone_out:
            v = res.get("international_format") or res.get("raw_format")
            if v:
                phone_out, phone_prov = v, "prospeo"
        elif "BetterContact" in nm and isinstance(res, dict) and not phone_out:
            data = res.get("data")
            if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("contact_phone_number"):
                phone_out, phone_prov = data[0]["contact_phone_number"], "bettercontact"
    return {"row": row_id, "email": email_out, "email_provider": email_prov,
            "phone": phone_out, "phone_provider": phone_prov}

results = {}
for x in runs:
    if x.get("status") != "completed":
        continue
    try:
        rec = harvest(x["runId"])
    except Exception as e:
        print("harvest err", x["runId"], e, flush=True)
        continue
    if rec and rec["row"]:
        results[rec["row"]] = rec
        print(f"  row {rec['row']}: email={rec['email'] or '-'}({rec['email_provider'] or '-'}) phone={rec['phone'] or '-'}({rec['phone_provider'] or '-'})", flush=True)

json.dump(results, open(os.path.join(HERE, "clay_results.json"), "w"), indent=2)

# ---- merge into rows ----
# Phone quality gates (toll-free, main line, line type, do-not-call) live in phone-compliance/phone_gate.py.
# DNC hash files: PHONE_DNC_FILES=/path/a.txt:/path/b.txt
sys.path.insert(0, os.path.join(HERE, "..", "phone-compliance"))
from phone_gate import CLEARED, PENDING, check_number, load_dnc  # noqa: E402
DNC = load_dnc([p for p in os.environ.get("PHONE_DNC_FILES", "").split(":") if p])
if DNC is None:
    print("warning: PHONE_DNC_FILES not set; phones marked pending_checks, do not dial until DNC runs", flush=True)

for r in rows:
    if r["ms_status"] == "ok":
        r["final_email"] = r["ms_email"]
        r["final_email_source"] = f"moltsets:{r['ms_risk']}"
        continue
    hit = results.get(str(r["row"]))
    if not hit:
        r["final_email"] = ""
        r["final_email_source"] = "clay_miss"
        continue
    if hit["email"] and hit["email"].lower() != r["bounced_email"].lower():
        r["final_email"] = hit["email"].lower()
        r["final_email_source"] = f"clay:{hit['email_provider']}"
    else:
        r["final_email"] = ""
        r["final_email_source"] = "clay_miss_same_or_none"
    route, reason, e164 = check_number(hit["phone"] or "", email=r.get("final_email", ""), dnc=DNC)
    r["clay_phone_route"], r["clay_phone_reason"] = route, reason
    if route in (CLEARED, PENDING):
        r["clay_phone"] = e164
        r["clay_phone_provider"] = hit["phone_provider"]
    else:
        r["clay_phone"] = ""
        r["clay_phone_provider"] = hit.get("phone_provider", "")

json.dump(rows, open(os.path.join(HERE, "final_rows.json"), "w"), indent=2)

# ---- summary ----
found_email = sum(1 for r in rows if r.get("final_email"))
found_phone = sum(1 for r in rows if r.get("clay_phone"))
print(f"\nFINAL: emails {found_email}/{len(rows)}, clay-only phones {found_phone}", flush=True)
for r in rows:
    print(f"  row {r['row']:>2} {r['full_name']:<22} email={r.get('final_email') or '-':<35} src={r.get('final_email_source') or '-':<22} phone={r.get('clay_phone') or '-'}", flush=True)
