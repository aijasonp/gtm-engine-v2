#!/usr/bin/env python3
"""Wire edges for the Floqer-mirror Clay workflow via incomingEdges on targets."""
import json, os, subprocess, sys

WORKFLOW_ID = "wf_0tl28zyd7nxzJMg5Nxf"
CLAY_BIN = os.path.expanduser("~/.local/bin/clay")

# node name -> id
N = {
    "Webhook": "wfn_REDACTED",
    "LinkedIn from email (2cr)": "wfn_REDACTED",
    "LinkedIn found?": "wfn_REDACTED",
    "LeadMagic (6cr)": "wfn_REDACTED",
    "LeadMagic found?": "wfn_REDACTED",
    "Wiza (7cr)": "wfn_REDACTED",
    "Wiza found?": "wfn_REDACTED",
    "Findymail (9cr)": "wfn_REDACTED",
    "Findymail found?": "wfn_REDACTED",
    "Prospeo (10cr)": "wfn_REDACTED",
    "Prospeo found?": "wfn_REDACTED",
    "Person Enrich (1cr)": "wfn_REDACTED",
    "Enriched Lead (output)": "wfn_REDACTED",
}

def cli(*args, timeout=120):
    proc = subprocess.run([CLAY_BIN, *args], capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"clay {' '.join(args)} failed ({proc.returncode}): {proc.stderr}")
    return json.loads(proc.stdout)

# Edges: (source_name, target_name, transition_id_or_None)
# For conditional sources, transition id must match context.transition_to(name, id)
EDGES = [
    ("Webhook", "LinkedIn from email (2cr)", None),
    ("LinkedIn from email (2cr)", "LinkedIn found?", None),
    ("LinkedIn found?", "LeadMagic (6cr)", "found"),
    ("LinkedIn found?", "LeadMagic (6cr)", "miss"),
    ("LeadMagic (6cr)", "LeadMagic found?", None),
    ("LeadMagic found?", "Person Enrich (1cr)", "found"),
    ("LeadMagic found?", "Wiza (7cr)", "miss"),
    ("Wiza (7cr)", "Wiza found?", None),
    ("Wiza found?", "Person Enrich (1cr)", "found"),
    ("Wiza found?", "Findymail (9cr)", "miss"),
    ("Findymail (9cr)", "Findymail found?", None),
    ("Findymail found?", "Person Enrich (1cr)", "found"),
    ("Findymail found?", "Prospeo (10cr)", "miss"),
    ("Prospeo (10cr)", "Prospeo found?", None),
    ("Prospeo found?", "Person Enrich (1cr)", "found"),
    ("Prospeo found?", "Person Enrich (1cr)", "miss"),
    ("Person Enrich (1cr)", "Enriched Lead (output)", None),
]

# Group incoming edges per target
from collections import defaultdict
target_edges = defaultdict(list)
for src, tgt, tid in EDGES:
    e = {"sourceNode": N[src]}
    if tid:
        e["transitionId"] = tid
        e["transitionName"] = tid
    target_edges[tgt].append(e)

for tgt, edges in target_edges.items():
    spec = json.dumps({"incomingEdges": edges})
    try:
        res = cli("workflows", "nodes", "update", WORKFLOW_ID, N[tgt], "--input", spec)
        print(f"wired {tgt}: {res.get('operation')}")
    except RuntimeError as e:
        print(f"FAILED {tgt}: {e}", file=sys.stderr)
