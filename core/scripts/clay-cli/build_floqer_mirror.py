#!/usr/bin/env python3
"""
Build the "Prospect Lead Enrichment (Floqer Mirror)" Clay workflow via the Clay CLI.

Mirrors the Floqer "Houston Contact Enrichment" chain (00000000-0000-0000-0000-000000000000):
  1. person_linkedin_url_by_email  -> find LinkedIn URL from email + name + company
  2. personal_phone_number_by_linkedin_url_waterfall -> cost-optimized phone waterfall
     (cheapest source first, escalate only on miss)
  3. person_enrich_by_floqer       -> full person enrichment (phone + email)

Clay equivalents (cheapest-first phone waterfall):
  - LinkedIn from email: wiza-find-linkedin-profile (2cr)
  - Phone waterfall:     leadmagic-find-mobile-number (6cr) -> wiza-find-phone (7cr)
                         -> findymail-find-mobile (9cr) -> prospeo-find-mobile-number (10cr)
  - Person enrich:       cpj-enrich-person (1cr)

Usage:
  python3 build_floqer_mirror.py            # build nodes + wire edges
  python3 build_floqer_mirror.py --dry-run   # print node specs without creating
"""
import argparse
import json
import os
import subprocess
import sys

WORKFLOW_ID = "wf_0tl28zyd7nxzJMg5Nxf"
TRIGGER_NODE = "wfn_REDACTED"
CLAY_BIN = os.path.expanduser("~/.local/bin/clay")

# --- Action package IDs (from clay workflows actions list) ---
PKG_WIZA = "00000000-0000-0000-0000-000000000000"
PKG_LEADMAGIC = "00000000-0000-0000-0000-000000000000"
PKG_FINDYMAIL = "00000000-0000-0000-0000-000000000000"
PKG_PROSPEO = "00000000-0000-0000-0000-000000000000"
PKG_CPJ = "00000000-0000-0000-0000-000000000000"


def cli(*args, timeout=120):
    proc = subprocess.run(
        [CLAY_BIN, *args], capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"clay {' '.join(args)} failed ({proc.returncode}): {proc.stderr}"
        )
    return json.loads(proc.stdout)


def tool_node(name, action_key, pkg_id, mapping, description=None):
    """Build a tool node spec (single clay_action)."""
    node = {
        "nodeType": "tool",
        "name": name,
        "tools": [
            {
                "toolType": "clay_action",
                "actionKey": action_key,
                "actionPackageId": pkg_id,
                "inputMappingConfig": mapping,
            }
        ],
    }
    if description:
        node["description"] = description
    return node


def code_conditional(name, code, description=None):
    node = {
        "nodeType": "conditional",
        "name": name,
        "conditionalMode": "code",
        "code": code,
    }
    if description:
        node["description"] = description
    return node


def code_node(name, code, description=None):
    node = {"nodeType": "code", "name": name, "code": code}
    if description:
        node["description"] = description
    return node


# --- Node definitions (in creation order; targets referenced by name must exist) ---

# Step 1: LinkedIn from email (mirror person_linkedin_url_by_email)
linkedin_from_email = tool_node(
    "LinkedIn from email (2cr)",
    "wiza-find-linkedin-profile",
    PKG_WIZA,
    {
        "email": {"type": "reference", "expression": "{{email}}"},
        "full_name": {"type": "reference", "expression": "{{first_name}} {{last_name}}"},
        "company": {"type": "reference", "expression": "{{company_name}}"},
        "domain": {"type": "reference", "expression": "{{company_domain}}"},
    },
    "Find a person's LinkedIn profile from their email + name + company (mirrors Floqer person_linkedin_url_by_email).",
)

# Gate: did we get a LinkedIn URL?
gate_linkedin = code_conditional(
    "LinkedIn found?",
    """def handler(context):
    try:
        branch = context.get_input("_branchOutputs") or {}
        linkedin = ""
        for node_id, out in branch.items():
            res = (out or {}).get("result") or {}
            data = res.get("data") or {}
            if data.get("linkedin_profile_url"):
                linkedin = data["linkedin_profile_url"]
                break
    except Exception:
        linkedin = ""
    if linkedin:
        context.transition_to("LeadMagic (6cr)", "found")
    else:
        context.transition_to("LeadMagic (6cr)", "miss")
    return {"linkedin_url": linkedin}""",
    "Determines whether a LinkedIn URL was found. Routes to the phone waterfall either way (LeadMagic can use name+domain fallback).",
)

# Step 2: Phone waterfall (cheapest first)
leadmagic = tool_node(
    "LeadMagic (6cr)",
    "leadmagic-find-mobile-number",
    PKG_LEADMAGIC,
    {
        "profile_url": {"type": "reference", "expression": "{{linkedin_url}}"},
    },
    "Find mobile number from LinkedIn profile (cheapest phone source, 6cr).",
)

gate_leadmagic = code_conditional(
    "LeadMagic found?",
    """def handler(context):
    try:
        branch = context.get_input("_branchOutputs") or {}
        phone = ""
        for node_id, out in branch.items():
            res = (out or {}).get("result") or {}
            if res.get("mobile_number"):
                phone = res["mobile_number"]
                break
    except Exception:
        phone = ""
    if phone:
        context.transition_to("Person Enrich (1cr)", "found")
    else:
        context.transition_to("Wiza (7cr)", "miss")
    return {"leadmagic_phone": phone}""",
    "If LeadMagic found a phone, proceed to person enrich; else escalate to Wiza.",
)

wiza = tool_node(
    "Wiza (7cr)",
    "wiza-find-phone",
    PKG_WIZA,
    {
        "full_name": {"type": "reference", "expression": "{{first_name}} {{last_name}}"},
        "domain": {"type": "reference", "expression": "{{company_domain}}"},
        "profile_url": {"type": "reference", "expression": "{{linkedin_url}}"},
    },
    "Find phone from name + domain (or LinkedIn URL), 7cr.",
)

gate_wiza = code_conditional(
    "Wiza found?",
    """def handler(context):
    try:
        branch = context.get_input("_branchOutputs") or {}
        phone = ""
        for node_id, out in branch.items():
            res = (out or {}).get("result") or {}
            data = res.get("data") or {}
            if data.get("mobile_phone") or data.get("phone_number"):
                phone = data.get("mobile_phone") or data.get("phone_number")
                break
    except Exception:
        phone = ""
    if phone:
        context.transition_to("Person Enrich (1cr)", "found")
    else:
        context.transition_to("Findymail (9cr)", "miss")
    return {"wiza_phone": phone}""",
    "If Wiza found a phone, proceed to person enrich; else escalate to Findymail.",
)

findymail = tool_node(
    "Findymail (9cr)",
    "findymail-find-mobile",
    PKG_FINDYMAIL,
    {
        "linkedin_url": {"type": "reference", "expression": "{{linkedin_url}}"},
    },
    "Find mobile from LinkedIn URL, 9cr.",
)

gate_findymail = code_conditional(
    "Findymail found?",
    """def handler(context):
    try:
        branch = context.get_input("_branchOutputs") or {}
        phone = ""
        for node_id, out in branch.items():
            res = (out or {}).get("result") or {}
            if res.get("mobilePhone"):
                phone = res["mobilePhone"]
                break
    except Exception:
        phone = ""
    if phone:
        context.transition_to("Person Enrich (1cr)", "found")
    else:
        context.transition_to("Prospeo (10cr)", "miss")
    return {"findymail_phone": phone}""",
    "If Findymail found a phone, proceed to person enrich; else escalate to Prospeo.",
)

prospeo = tool_node(
    "Prospeo (10cr)",
    "prospeo-find-mobile-number",
    PKG_PROSPEO,
    {
        "personal_linkedin_url": {"type": "reference", "expression": "{{linkedin_url}}"},
    },
    "Find mobile from LinkedIn URL (most expensive phone source, 10cr).",
)

gate_prospeo = code_conditional(
    "Prospeo found?",
    """def handler(context):
    try:
        branch = context.get_input("_branchOutputs") or {}
        phone = ""
        for node_id, out in branch.items():
            res = (out or {}).get("result") or {}
            if res.get("international_format") or res.get("raw_format"):
                phone = res.get("international_format") or res.get("raw_format")
                break
    except Exception:
        phone = ""
    if phone:
        context.transition_to("Person Enrich (1cr)", "found")
    else:
        context.transition_to("Person Enrich (1cr)", "miss")
    return {"prospeo_phone": phone}""",
    "If Prospeo found a phone, proceed to person enrich; else proceed anyway (last source).",
)

# Step 3: Person enrich (mirror person_enrich_by_floqer)
person_enrich = tool_node(
    "Person Enrich (1cr)",
    "cpj-enrich-person",
    PKG_CPJ,
    {
        "person_identifier": {"type": "reference", "expression": "{{linkedin_url}}"},
        "email": {"type": "reference", "expression": "{{email}}"},
    },
    "Full person enrichment from LinkedIn URL or email (mirrors Floqer person_enrich_by_floqer), 1cr.",
)

# Output: assemble final record
output_node = code_node(
    "Enriched Lead (output)",
    """def handler(context):
    first = context.get_input("first_name") or ""
    last = context.get_input("last_name") or ""
    company = context.get_input("company_name") or ""
    title = context.get_input("job_title") or ""
    email = context.get_input("email") or ""
    linkedin = context.get_input("linkedin_url") or ""
    phone = context.get_input("phone") or ""
    # Pull enriched phone from whichever finder in the waterfall found it
    try:
        branch = context.get_input("_branchOutputs") or {}
        for node_id, out in branch.items():
            res = (out or {}).get("result") or {}
            # LeadMagic
            if res.get("mobile_number"):
                phone = res["mobile_number"]
                break
            # Wiza
            data = res.get("data") or {}
            if data.get("mobile_phone") or data.get("phone_number"):
                phone = data.get("mobile_phone") or data.get("phone_number")
                break
            # Findymail
            if res.get("mobilePhone"):
                phone = res["mobilePhone"]
                break
            # Prospeo
            if res.get("international_format") or res.get("raw_format"):
                phone = res.get("international_format") or res.get("raw_format")
                break
            # Person enrich (cpj) - no phone, but may refine linkedin/name
            if res.get("url"):
                linkedin = res["url"]
    except Exception:
        pass
    return {
        "first_name": first,
        "last_name": last,
        "company_name": company,
        "job_title": title,
        "email": email,
        "phone": phone,
        "linkedin_url": linkedin,
        "enriched": True,
    }""",
    "Assembles the final enriched lead record (email, phone, LinkedIn URL) for downstream outreach.",
)

# Order of creation (targets referenced by name must exist before sources that
# transition_to them, so create output + person_enrich first, then waterfall back to front)
NODES = [
    output_node,          # terminal
    person_enrich,        # feeds output
    gate_prospeo,        # feeds person_enrich
    prospeo,             # feeds gate_prospeo
    gate_findymail,      # feeds prospeo
    findymail,           # feeds gate_findymail
    gate_wiza,           # feeds findymail
    wiza,                # feeds gate_wiza
    gate_leadmagic,      # feeds wiza
    leadmagic,           # feeds gate_leadmagic
    gate_linkedin,       # feeds leadmagic
    linkedin_from_email, # feeds gate_linkedin
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        for n in NODES:
            print(json.dumps(n, indent=2))
            print("---")
        return

    created = {}
    for node in NODES:
        spec = json.dumps(node)
        try:
            res = cli("workflows", "nodes", "create", WORKFLOW_ID, "--input", spec)
            nid = res.get("nodeId")
            created[node["name"]] = nid
            print(f"created: {node['name']} -> {nid}")
        except RuntimeError as e:
            print(f"FAILED: {node['name']}: {e}", file=sys.stderr)
            # continue to create the rest; report at end

    print("\n--- Created node IDs ---")
    print(json.dumps(created, indent=2))
    print("\nTrigger node:", TRIGGER_NODE)


if __name__ == "__main__":
    main()
