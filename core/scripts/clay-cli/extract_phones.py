#!/usr/bin/env python3
"""Extract enriched phones from Clay BDR Call-Down run steps.

The workflow's terminal output node drops the found phone (known bug). The
actual enriched value lives in the per-step outputs of the enrichment nodes
(Lyne/Wiza/BetterContact). This reads every run's steps and pulls the phone.
"""
import json, os, subprocess, sys

CLAY = os.path.expanduser("~/.local/bin/clay")
WF = "wf_0tk4qbqMNmp6wBdmKnc"

def cli(*args):
    proc = subprocess.run([CLAY, *args], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"clay {' '.join(args)} failed: {proc.stderr}")
    return json.loads(proc.stdout)

# Get all run ids
runs = cli("workflows", "runs", "list", WF).get("data", [])
print(f"Total runs: {len(runs)}")

results = []
for r in runs:
    run_id = r["runId"]
    try:
        steps = cli("workflows", "runs", "steps", WF, run_id).get("data", [])
    except RuntimeError as e:
        print(f"  [warn] {run_id}: {e}", file=sys.stderr)
        continue
    # Find the enrichment step (Lyne/Wiza/BetterContact) that produced a phone
    phone = ""
    email = ""
    for s in steps:
        node = s.get("nodeName", "")
        outs = s.get("stepOutputs", {}) or {}
        # capture email from webhook step
        if node == "Webhook" and not email:
            email = outs.get("email", "")
        # enrichment nodes
        if any(k in node for k in ("Lyne", "Wiza", "BetterContact", "enrich")):
            # phone may be nested
            ph = outs.get("phone") or outs.get("phone_number") or ""
            if not ph and isinstance(outs.get("structuredOutputs"), dict):
                ph = outs["structuredOutputs"].get("phone") or outs["structuredOutputs"].get("phone_number") or ""
            if ph:
                phone = ph
    results.append({"run_id": run_id, "email": email, "phone": phone})

# Summary
found = [r for r in results if r["phone"]]
print(f"Runs with phone found: {len(found)}/{len(results)}")
for r in found:
    print(f"  {r['email']} -> {r['phone']}")

with open("/tmp/nyc_clay_phones.json", "w") as f:
    json.dump(results, f, indent=2)
print("Wrote /tmp/nyc_clay_phones.json")
