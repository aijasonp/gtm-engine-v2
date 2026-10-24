#!/usr/bin/env python3
"""
BDR Call-Down Enrichment runner (Clay CLI / Public API).

Drives the "BDR Call-Down Enrichment" Clay workflow autonomously, mirroring how
we run Smartlead: the GTM agent generates leads -> push to Clay -> poll -> get the
ready-to-call list back (enriched with phone/email where missing).

Flow:
  1. Read leads from a JSON/CSV input (GTM agent's daily call-down list).
  2. POST each lead to the Clay webhook trigger (only those missing a phone get
     enriched; the workflow's gate handles that).
  3. Poll the workflow run(s) to completion.
  4. Emit the ready-to-call list (name, title, company, email, phone) as JSON.

Usage:
  python3 run_bdr_call_down.py --input leads.json [--output ready.json]
  python3 run_bdr_call_down.py --input leads.csv [--output ready.json]

Input JSON shape (array of objects):
  [{"first_name","last_name","company_name","company_domain","job_title","email","phone"}, ...]

Env:
  CLAY_API_KEY  (optional; falls back to `clay` CLI auth for interactive use)
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.request

WORKFLOW_ID = "wf_0tk4qbqMNmp6wBdmKnc"
WEBHOOK_URL = "https://api.clay.com/v3/sources/webhook/00000000-0000-0000-0000-000000000000"
CLAY_BIN = os.path.expanduser("~/.local/bin/clay")


def load_leads(path):
    """Load leads from JSON (array) or CSV."""
    if path.endswith(".csv"):
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("leads", data.get("data", []))
    return data


def push_to_webhook(lead):
    """POST one lead to the Clay webhook trigger. Returns HTTP status."""
    body = json.dumps(lead).encode()
    req = urllib.request.Request(
        WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def cli(*args, timeout=120):
    """Run a `clay` CLI command, return parsed JSON."""
    proc = subprocess.run(
        [CLAY_BIN, *args], capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        raise RuntimeError(f"clay {' '.join(args)} failed ({proc.returncode}): {proc.stderr}")
    return json.loads(proc.stdout)


def run_workflow(leads):
    """Start a manual test run of the workflow with the given leads as inputs.

    The workflow's webhook trigger accepts one lead per POST. For a batch, we
    start one run per lead (the gate routes each to enrich or ready).
    Returns list of run ids.
    """
    run_ids = []
    for lead in leads:
        # Start a manual run with this lead as input
        proc = subprocess.run(
            [CLAY_BIN, "workflows", "runs", "test", WORKFLOW_ID, "--inputs", "-"],
            input=json.dumps(lead), capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            print(f"  [warn] run start failed for {lead.get('email')}: {proc.stderr}", file=sys.stderr)
            continue
        run_id = json.loads(proc.stdout).get("runId")
        run_ids.append(run_id)
    return run_ids


def wait_for_run(run_id, timeout=300):
    """Poll a workflow run to completion. Returns final status."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            d = cli("workflows", "runs", "get", WORKFLOW_ID, run_id)
        except RuntimeError:
            time.sleep(5)
            continue
        status = d.get("status")
        if status in ("completed", "failed", "cancelled", "paused"):
            return status
        time.sleep(5)
    return "timeout"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="leads JSON or CSV")
    ap.add_argument("--output", help="ready-to-call JSON output path")
    ap.add_argument("--push-only", action="store_true", help="POST to webhook only, no run/poll")
    args = ap.parse_args()

    leads = load_leads(args.input)
    print(f"Loaded {len(leads)} leads from {args.input}")

    if args.push_only:
        # Push each lead to the webhook; the workflow's own trigger handles runs.
        ok = 0
        for lead in leads:
            status = push_to_webhook(lead)
            if 200 <= status < 300:
                ok += 1
            else:
                print(f"  [warn] webhook {status} for {lead.get('email')}", file=sys.stderr)
        print(f"Pushed {ok}/{len(leads)} leads to Clay webhook")
        return

    # Start a run per lead (manual test path exercises the draft)
    run_ids = run_workflow(leads)
    print(f"Started {len(run_ids)} workflow runs")

    results = []
    for run_id in run_ids:
        status = wait_for_run(run_id)
        print(f"  run {run_id}: {status}")
        if status == "completed":
            # Pull the terminal output node's result
            d = cli("workflows", "runs", "get", WORKFLOW_ID, run_id, "--verbose")
            for node in d.get("nodes", []):
                out = node.get("outputs") or node.get("output") or {}
                if out.get("ready_to_call"):
                    results.append(out)
                    break

    print(f"\nReady-to-call: {len(results)} leads")
    for r in results:
        print(f"  {r.get('first_name')} {r.get('last_name')} | {r.get('job_title')} | "
              f"{r.get('company_name')} | {r.get('email')} | {r.get('phone')}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
