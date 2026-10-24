#!/usr/bin/env python3
"""Set outgoingEdges (with transitionId) on conditional source nodes."""
import json, os, subprocess, sys

WORKFLOW_ID = "wf_0tl28zyd7nxzJMg5Nxf"
CLAY_BIN = os.path.expanduser("~/.local/bin/clay")

N = {
    "LinkedIn found?": "wfn_REDACTED",
    "LeadMagic found?": "wfn_REDACTED",
    "Wiza found?": "wfn_REDACTED",
    "Findymail found?": "wfn_REDACTED",
    "Prospeo found?": "wfn_REDACTED",
    "LeadMagic (6cr)": "wfn_REDACTED",
    "Wiza (7cr)": "wfn_REDACTED",
    "Findymail (9cr)": "wfn_REDACTED",
    "Prospeo (10cr)": "wfn_REDACTED",
    "Person Enrich (1cr)": "wfn_REDACTED",
}

def cli(*args, timeout=120):
    proc = subprocess.run([CLAY_BIN, *args], capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"clay {' '.join(args)} failed ({proc.returncode}): {proc.stderr}")
    return json.loads(proc.stdout)

# conditional source -> [(transition_id, target_name)]
COND = {
    "LinkedIn found?": [("found", "LeadMagic (6cr)"), ("miss", "LeadMagic (6cr)")],
    "LeadMagic found?": [("found", "Person Enrich (1cr)"), ("miss", "Wiza (7cr)")],
    "Wiza found?": [("found", "Person Enrich (1cr)"), ("miss", "Findymail (9cr)")],
    "Findymail found?": [("found", "Person Enrich (1cr)"), ("miss", "Prospeo (10cr)")],
    "Prospeo found?": [("found", "Person Enrich (1cr)"), ("miss", "Person Enrich (1cr)")],
}

for src, routes in COND.items():
    edges = []
    for tid, tgt in routes:
        edges.append({"targetNode": N[tgt], "transitionId": tid, "transitionName": tid})
    spec = json.dumps({"outgoingEdges": edges})
    try:
        res = cli("workflows", "nodes", "update", WORKFLOW_ID, N[src], "--input", spec)
        print(f"wired {src}: {res.get('operation')}")
    except RuntimeError as e:
        print(f"FAILED {src}: {e}", file=sys.stderr)
