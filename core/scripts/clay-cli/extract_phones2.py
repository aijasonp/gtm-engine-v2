#!/usr/bin/env python3
"""Extract enriched phones from Clay BDR Call-Down run steps (correct keys).

The enrichment nodes output lyne_phone / wiza_phone (not 'phone'). This reads
every run's steps and pulls the actual found phone.
"""
import json, os, subprocess

CLAY = os.path.expanduser("~/.local/bin/clay")
WF = "wf_0tk4qbqMNmp6wBdmKnc"

def cli(*args):
    p = subprocess.run([CLAY, *args], capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError(f"clay {' '.join(args)} failed: {p.stderr}")
    return json.loads(p.stdout)

runs = cli("workflows", "runs", "list", WF).get("data", [])
print("runs:", len(runs))

phones = {}
for r in runs:
    rid = r["runId"]
    try:
        steps = cli("workflows", "runs", "steps", WF, rid).get("data", [])
    except RuntimeError:
        continue
    email = ""
    ph = ""
    for s in steps:
        node = s.get("nodeName", "")
        outs = s.get("stepOutputs") or {}
        so = outs.get("structuredOutputs") or {}
        if node == "Webhook" and not email:
            email = outs.get("email", "")
        if so.get("lyne_phone"):
            ph = so["lyne_phone"]
        if so.get("wiza_phone"):
            ph = so["wiza_phone"]
        if outs.get("phone") and node != "Webhook":
            ph = outs["phone"]
    if ph:
        phones[email] = ph

print("runs with phone:", len(phones))
for e, p in phones.items():
    print(" ", e, "->", p)
with open("/tmp/nyc_clay_phones2.json", "w") as f:
    json.dump(phones, f, indent=2)
print("Wrote /tmp/nyc_clay_phones2.json")
