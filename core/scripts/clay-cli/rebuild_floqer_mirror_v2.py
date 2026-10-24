#!/usr/bin/env python3
"""
Rebuild the Floqer-mirror Clay workflow CORRECTLY.

Verified working pattern (from scratch tests):
- Conditional nodes use SINGLE-ARG transition_to("NodeName") — the CLI strips
  transitionId from edges, so two-arg transition_to(name, id) fails at runtime.
- Edges are wired via incomingEdges on the TARGET node (outgoingEdges is ignored).
- Trigger wired via incomingEdges using the trigger's workflowNodeId.

Chain (mirrors Floqer "Houston Contact Enrichment"):
  LinkedIn from email (wiza, 2cr) -> LinkedIn found? ->
  LeadMagic (6cr) -> LeadMagic found? ->
  Wiza (7cr) -> Wiza found? ->
  Findymail (9cr) -> Findymail found? ->
  Prospeo (10cr) -> Prospeo found? ->
  Person Enrich (cpj, 1cr) -> Enriched Lead (output)
"""
import json, os, subprocess, sys, time

CLAY_BIN = os.path.expanduser("~/.local/bin/clay")

PKG_WIZA = "00000000-0000-0000-0000-000000000000"
PKG_LEADMAGIC = "00000000-0000-0000-0000-000000000000"
PKG_FINDYMAIL = "00000000-0000-0000-0000-000000000000"
PKG_PROSPEO = "00000000-0000-0000-0000-000000000000"
PKG_CPJ = "00000000-0000-0000-0000-000000000000"

def cli(*args, timeout=120, retries=4):
    last = None
    for attempt in range(retries):
        proc = subprocess.run([CLAY_BIN, *args], capture_output=True, text=True, timeout=timeout)
        if proc.returncode == 0:
            try:
                return json.loads(proc.stdout)
            except json.JSONDecodeError:
                last = RuntimeError(f"clay {' '.join(args)} bad JSON: {proc.stdout[:200]}")
        else:
            last = RuntimeError(f"clay {' '.join(args)} failed ({proc.returncode}): {proc.stderr}")
            # retry on transient server errors
            if 'server_error' in proc.stderr or '<html' in proc.stderr.lower():
                time.sleep(2 * (attempt + 1))
                continue
            raise last
        time.sleep(2 * (attempt + 1))
    raise last

def tool_node(name, action_key, pkg_id, mapping, description=None):
    node = {"nodeType": "tool", "name": name,
            "tools": [{"toolType": "clay_action", "actionKey": action_key,
                       "actionPackageId": pkg_id, "inputMappingConfig": mapping}]}
    if description: node["description"] = description
    return node

def cond_node(name, code, description=None):
    node = {"nodeType": "conditional", "name": name, "conditionalMode": "code", "code": code}
    if description: node["description"] = description
    return node

def code_node(name, code, description=None):
    node = {"nodeType": "code", "name": name, "code": code}
    if description: node["description"] = description
    return node

# --- Node definitions ---
linkedin_from_email = tool_node(
    "LinkedIn from email (2cr)", "wiza-find-linkedin-profile", PKG_WIZA,
    {"email": {"type": "reference", "expression": "{{email}}"},
     "full_name": {"type": "reference", "expression": "{{first_name}} {{last_name}}"},
     "company": {"type": "reference", "expression": "{{company_name}}"},
     "domain": {"type": "reference", "expression": "{{company_domain}}"}},
    "Find LinkedIn URL from email + name + company (mirrors Floqer person_linkedin_url_by_email).")

gate_linkedin = cond_node(
    "LinkedIn found?",
    'def handler(context):\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        linkedin = ""\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            data = res.get("data") or {}\n'
    '            if data.get("linkedin_profile_url"):\n'
    '                linkedin = data["linkedin_profile_url"]\n'
    '                break\n'
    '    except Exception:\n'
    '        linkedin = ""\n'
    '    context.transition_to("LeadMagic (6cr)")\n'
    '    return {"linkedin_url": linkedin}',
    "Routes to phone waterfall (LeadMagic can use name+domain fallback).")

leadmagic = tool_node(
    "LeadMagic (6cr)", "leadmagic-find-mobile-number", PKG_LEADMAGIC,
    {"profile_url": {"type": "reference", "expression": "{{linkedin_url}}"}},
    "Find mobile from LinkedIn profile (cheapest phone source, 6cr).")

gate_leadmagic = cond_node(
    "LeadMagic found?",
    'def handler(context):\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        phone = ""\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            if res.get("mobile_number"):\n'
    '                phone = res["mobile_number"]\n'
    '                break\n'
    '    except Exception:\n'
    '        phone = ""\n'
    '    if phone:\n'
    '        context.transition_to("Person Enrich (1cr)")\n'
    '    else:\n'
    '        context.transition_to("Wiza (7cr)")\n'
    '    return {"leadmagic_phone": phone}',
    "If LeadMagic found a phone, enrich; else escalate to Wiza.")

wiza = tool_node(
    "Wiza (7cr)", "wiza-find-phone", PKG_WIZA,
    {"full_name": {"type": "reference", "expression": "{{first_name}} {{last_name}}"},
     "domain": {"type": "reference", "expression": "{{company_domain}}"},
     "profile_url": {"type": "reference", "expression": "{{linkedin_url}}"}},
    "Find phone from name + domain (or LinkedIn URL), 7cr.")

gate_wiza = cond_node(
    "Wiza found?",
    'def handler(context):\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        phone = ""\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            data = res.get("data") or {}\n'
    '            if data.get("mobile_phone") or data.get("phone_number"):\n'
    '                phone = data.get("mobile_phone") or data.get("phone_number")\n'
    '                break\n'
    '    except Exception:\n'
    '        phone = ""\n'
    '    if phone:\n'
    '        context.transition_to("Person Enrich (1cr)")\n'
    '    else:\n'
    '        context.transition_to("Findymail (9cr)")\n'
    '    return {"wiza_phone": phone}',
    "If Wiza found a phone, enrich; else escalate to Findymail.")

findymail = tool_node(
    "Findymail (9cr)", "findymail-find-mobile", PKG_FINDYMAIL,
    {"linkedin_url": {"type": "reference", "expression": "{{linkedin_url}}"}},
    "Find mobile from LinkedIn URL, 9cr.")

gate_findymail = cond_node(
    "Findymail found?",
    'def handler(context):\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        phone = ""\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            if res.get("mobilePhone"):\n'
    '                phone = res["mobilePhone"]\n'
    '                break\n'
    '    except Exception:\n'
    '        phone = ""\n'
    '    if phone:\n'
    '        context.transition_to("Person Enrich (1cr)")\n'
    '    else:\n'
    '        context.transition_to("Prospeo (10cr)")\n'
    '    return {"findymail_phone": phone}',
    "If Findymail found a phone, enrich; else escalate to Prospeo.")

prospeo = tool_node(
    "Prospeo (10cr)", "prospeo-find-mobile-number", PKG_PROSPEO,
    {"personal_linkedin_url": {"type": "reference", "expression": "{{linkedin_url}}"}},
    "Find mobile from LinkedIn URL (most expensive phone source, 10cr).")

gate_prospeo = cond_node(
    "Prospeo found?",
    'def handler(context):\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        phone = ""\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            if res.get("international_format") or res.get("raw_format"):\n'
    '                phone = res.get("international_format") or res.get("raw_format")\n'
    '                break\n'
    '    except Exception:\n'
    '        phone = ""\n'
    '    if phone:\n'
    '        context.transition_to("Person Enrich (1cr)")\n'
    '    else:\n'
    '        context.transition_to("Person Enrich (1cr)")\n'
    '    return {"prospeo_phone": phone}',
    "If Prospeo found a phone, enrich; else proceed anyway (last source).")

person_enrich = tool_node(
    "Person Enrich (1cr)", "cpj-enrich-person", PKG_CPJ,
    {"person_identifier": {"type": "reference", "expression": "{{linkedin_url}}"},
     "email": {"type": "reference", "expression": "{{email}}"}},
    "Full person enrichment from LinkedIn URL or email (mirrors Floqer person_enrich_by_floqer), 1cr.")

output_node = code_node(
    "Enriched Lead (output)",
    'def handler(context):\n'
    '    first = context.get_input("first_name") or ""\n'
    '    last = context.get_input("last_name") or ""\n'
    '    company = context.get_input("company_name") or ""\n'
    '    title = context.get_input("job_title") or ""\n'
    '    email = context.get_input("email") or ""\n'
    '    linkedin = context.get_input("linkedin_url") or ""\n'
    '    phone = context.get_input("phone") or ""\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            if res.get("mobile_number"):\n'
    '                phone = res["mobile_number"]\n'
    '                break\n'
    '            data = res.get("data") or {}\n'
    '            if data.get("mobile_phone") or data.get("phone_number"):\n'
    '                phone = data.get("mobile_phone") or data.get("phone_number")\n'
    '                break\n'
    '            if res.get("mobilePhone"):\n'
    '                phone = res["mobilePhone"]\n'
    '                break\n'
    '            if res.get("international_format") or res.get("raw_format"):\n'
    '                phone = res.get("international_format") or res.get("raw_format")\n'
    '                break\n'
    '            if res.get("url"):\n'
    '                linkedin = res["url"]\n'
    '    except Exception:\n'
    '        pass\n'
    '    return {\n'
    '        "first_name": first, "last_name": last, "company_name": company,\n'
    '        "job_title": title, "email": email, "phone": phone,\n'
    '        "linkedin_url": linkedin, "enriched": True,\n'
    '    }',
    "Assembles the final enriched lead record (email, phone, LinkedIn URL).")

# Creation order: targets before sources that transition_to them
NODES = [
    output_node, person_enrich, gate_prospeo, prospeo, gate_findymail,
    findymail, gate_wiza, wiza, gate_leadmagic, leadmagic, gate_linkedin,
    linkedin_from_email,
]

def main():
    name = "Prospect Lead Enrichment (Floqer Mirror) v2"
    wf = cli("workflows", "create", "--name", name)
    wfid = wf["id"]
    print(f"created workflow {wfid}")

    created = {}
    for node in NODES:
        res = cli("workflows", "nodes", "create", wfid, "--input", json.dumps(node))
        created[node["name"]] = res["nodeId"]
        print(f"  created {node['name']} -> {res['nodeId']}")

    # Wire edges via incomingEdges on targets (single-arg transition_to)
    # (source_name, target_name)
    EDGES = [
        ("LinkedIn from email (2cr)", "LinkedIn found?"),
        ("LinkedIn found?", "LeadMagic (6cr)"),
        ("LeadMagic (6cr)", "LeadMagic found?"),
        ("LeadMagic found?", "Person Enrich (1cr)"),
        ("LeadMagic found?", "Wiza (7cr)"),
        ("Wiza (7cr)", "Wiza found?"),
        ("Wiza found?", "Person Enrich (1cr)"),
        ("Wiza found?", "Findymail (9cr)"),
        ("Findymail (9cr)", "Findymail found?"),
        ("Findymail found?", "Person Enrich (1cr)"),
        ("Findymail found?", "Prospeo (10cr)"),
        ("Prospeo (10cr)", "Prospeo found?"),
        ("Prospeo found?", "Person Enrich (1cr)"),
        ("Person Enrich (1cr)", "Enriched Lead (output)"),
    ]
    from collections import defaultdict
    target_edges = defaultdict(list)
    for src, tgt in EDGES:
        target_edges[tgt].append({"sourceNode": created[src]})
    for tgt, edges in target_edges.items():
        cli("workflows", "nodes", "update", wfid, created[tgt], "--input",
            json.dumps({"incomingEdges": edges}))
        print(f"  wired -> {tgt}")

    # Manual trigger
    trig = cli("workflows", "triggers", "create", wfid, "--input", json.dumps({
        "triggerType": "manual",
        "inputSchema": {"type": "object", "properties": {
            "email": {"type": "string"}, "first_name": {"type": "string"},
            "last_name": {"type": "string"}, "company_name": {"type": "string"},
            "company_domain": {"type": "string"}, "linkedin_url": {"type": "string"},
            "job_title": {"type": "string"}, "phone": {"type": "string"}}}}))
    trig_id = trig["resourceId"]
    trig_node = cli("workflows", "triggers", "get", trig_id)["workflowNodeId"]
    cli("workflows", "nodes", "update", wfid, created["LinkedIn from email (2cr)"],
        "--input", json.dumps({"incomingEdges": [{"sourceNode": trig_node}]}))
    print(f"  wired trigger -> LinkedIn from email")

    # Validate
    val = cli("workflows", "graph", "validate", wfid)
    print("validate:", json.dumps(val))

    # Publish
    pub = cli("workflows", "publish", wfid, "--name", name)
    print("published:", json.dumps(pub.get("publishedVersion")))

    # Register routine
    try:
        rt = cli("routines", "create", "workflow", wfid, "--name", name)
        print("routine:", rt["id"])
    except RuntimeError as e:
        print("routine (may already exist):", e)

    print("WORKFLOW_ID=" + wfid)
    print("URL=" + wf["url"])

if __name__ == "__main__":
    main()
