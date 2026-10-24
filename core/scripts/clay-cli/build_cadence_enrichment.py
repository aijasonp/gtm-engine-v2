#!/usr/bin/env python3
"""
Build the Cadence Contact Enrichment workflow (email + mobile waterfall).

Purpose: {{AE_4}} prospecting cadence (sheet REDACTED_GOOGLE_ID).
  In:  first_name, last_name, full_name, company_name, company_domain, job_title,
       linkedin_url, email (may be blank), row
  Out: terminal code node returns {row, email, mobile_phone, linkedin_url,
       email_source, phone_source}. The GTM agent polls runs via CLI and writes results
       back to the sheet. No HTTP callback (keeps prod webhook server untouched).

Chain (mirrors rebuild_floqer_mirror_v2.py verified pattern):
  Trigger (webhook)
    -> [if email blank] LeadMagic email (1cr) -> Findymail email (2cr) -> Datagma email (2cr)
    -> Lyne mobile (4cr, first-party, takes LinkedIn URL or email)
    -> Wiza mobile (7cr)
    -> Findymail mobile (9cr)
    -> Prospeo mobile (10cr)
    -> BetterContact mobile (30cr, last resort)
    -> Build Callback Payload (code)
    -> Callback to the GTM agent (HTTP)

Cost per contact (worst case, all fire): ~65cr. Expected average ~15-25cr
(waterfall short-circuits on first hit).
"""
import json, os, subprocess, sys, time

CLAY_BIN = os.path.expanduser("~/.local/bin/clay-bin")

PKG_LEADMAGIC = "00000000-0000-0000-0000-000000000000"
PKG_FINDYMAIL = "00000000-0000-0000-0000-000000000000"
PKG_DATAGMA   = "00000000-0000-0000-0000-000000000000"
PKG_LYNE      = "00000000-0000-0000-0000-000000000000"
PKG_WIZA      = "00000000-0000-0000-0000-000000000000"
PKG_PROSPEO   = "00000000-0000-0000-0000-000000000000"
PKG_BETTER    = "00000000-0000-0000-0000-000000000000"


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

# ============ EMAIL CHAIN (only fires when inbound email is blank) ============

gate_need_email = cond_node(
    "Need email?",
    'def handler(context):\n'
    '    email = (context.get_input("email") or "").strip()\n'
    '    if email:\n'
    '        context.transition_to("Lyne mobile (4cr)")\n'
    '    else:\n'
    '        context.transition_to("LeadMagic email (1cr)")\n'
    '    return {"input_email": email}',
    "If inbound email exists, skip email waterfall and go straight to mobile."
)

leadmagic_email = tool_node(
    "LeadMagic email (1cr)", "leadmagic-find-work-email", PKG_LEADMAGIC,
    {"name": {"type": "reference", "expression": "{{full_name}}"},
     "domain": {"type": "reference", "expression": "{{company_domain}}"}},
    "Cheapest work-email finder (1cr)."
)

gate_leadmagic_email = cond_node(
    "LeadMagic email found?",
    'def handler(context):\n'
    '    email = ""\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            if res.get("email"):\n'
    '                email = res["email"]\n'
    '                break\n'
    '    except Exception:\n'
    '        pass\n'
    '    if email:\n'
    '        context.transition_to("Lyne mobile (4cr)")\n'
    '    else:\n'
    '        context.transition_to("Findymail email (2cr)")\n'
    '    return {"leadmagic_email": email}',
    "If LeadMagic found an email, proceed to mobile. Else escalate."
)

findymail_email = tool_node(
    "Findymail email (2cr)", "findymail-find-work-email", PKG_FINDYMAIL,
    {"full_name": {"type": "reference", "expression": "{{full_name}}"},
     "company_domain": {"type": "reference", "expression": "{{company_domain}}"}},
    "Findymail work email (2cr)."
)

gate_findymail_email = cond_node(
    "Findymail email found?",
    'def handler(context):\n'
    '    email = ""\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            if res.get("email"):\n'
    '                email = res["email"]\n'
    '                break\n'
    '    except Exception:\n'
    '        pass\n'
    '    if email:\n'
    '        context.transition_to("Lyne mobile (4cr)")\n'
    '    else:\n'
    '        context.transition_to("Datagma email (2cr)")\n'
    '    return {"findymail_email": email}',
    "If Findymail found an email, proceed to mobile. Else last email source."
)

datagma_email = tool_node(
    "Datagma email (2cr)", "datagma-find-work-email-v3", PKG_DATAGMA,
    {"full_name": {"type": "reference", "expression": "{{full_name}}"},
     "company_domain": {"type": "reference", "expression": "{{company_domain}}"}},
    "Datagma work email v3 (2cr, last email source)."
)

gate_datagma_email = cond_node(
    "Datagma email found?",
    'def handler(context):\n'
    '    email = ""\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            if res.get("email"):\n'
    '                email = res["email"]\n'
    '                break\n'
    '    except Exception:\n'
    '        pass\n'
    '    context.transition_to("Lyne mobile (4cr)")\n'
    '    return {"datagma_email": email}',
    "Last email source. Proceed to mobile regardless."
)

# ============ MOBILE CHAIN (always runs) ============

lyne_mobile = tool_node(
    "Lyne mobile (4cr)", "lyne-find-mobile-number", PKG_LYNE,
    {"search_input": {"type": "reference", "expression": "{{linkedin_url}}"}},
    "Clay first-party mobile finder. Takes LinkedIn URL (preferred) or email."
)

gate_lyne = cond_node(
    "Lyne found?",
    'def handler(context):\n'
    '    phone = ""\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            if res.get("mobile_phone"):\n'
    '                phone = res["mobile_phone"]\n'
    '                break\n'
    '    except Exception:\n'
    '        pass\n'
    '    if phone:\n'
    '        context.transition_to("Build Callback Payload")\n'
    '    else:\n'
    '        context.transition_to("Wiza mobile (7cr)")\n'
    '    return {"lyne_phone": phone}',
    "If Lyne found a mobile, build payload. Else escalate."
)

wiza_mobile = tool_node(
    "Wiza mobile (7cr)", "wiza-find-phone", PKG_WIZA,
    {"full_name": {"type": "reference", "expression": "{{full_name}}"},
     "domain": {"type": "reference", "expression": "{{company_domain}}"},
     "profile_url": {"type": "reference", "expression": "{{linkedin_url}}"}},
    "Wiza phone finder (7cr)."
)

gate_wiza = cond_node(
    "Wiza found?",
    'def handler(context):\n'
    '    phone = ""\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            data = res.get("data") or {}\n'
    '            if data.get("mobile_phone") or data.get("phone_number"):\n'
    '                phone = data.get("mobile_phone") or data.get("phone_number")\n'
    '                break\n'
    '    except Exception:\n'
    '        pass\n'
    '    if phone:\n'
    '        context.transition_to("Build Callback Payload")\n'
    '    else:\n'
    '        context.transition_to("Findymail mobile (9cr)")\n'
    '    return {"wiza_phone": phone}',
    "If Wiza found a mobile, build payload. Else escalate."
)

findymail_mobile = tool_node(
    "Findymail mobile (9cr)", "findymail-find-mobile", PKG_FINDYMAIL,
    {"linkedin_url": {"type": "reference", "expression": "{{linkedin_url}}"}},
    "Findymail mobile from LinkedIn URL (9cr)."
)

gate_findymail = cond_node(
    "Findymail found?",
    'def handler(context):\n'
    '    phone = ""\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            if res.get("mobilePhone"):\n'
    '                phone = res["mobilePhone"]\n'
    '                break\n'
    '    except Exception:\n'
    '        pass\n'
    '    if phone:\n'
    '        context.transition_to("Build Callback Payload")\n'
    '    else:\n'
    '        context.transition_to("Prospeo mobile (10cr)")\n'
    '    return {"findymail_phone": phone}',
    "If Findymail found a mobile, build payload. Else escalate."
)

prospeo_mobile = tool_node(
    "Prospeo mobile (10cr)", "prospeo-find-mobile-number", PKG_PROSPEO,
    {"personal_linkedin_url": {"type": "reference", "expression": "{{linkedin_url}}"}},
    "Prospeo mobile from LinkedIn URL (10cr)."
)

gate_prospeo = cond_node(
    "Prospeo found?",
    'def handler(context):\n'
    '    phone = ""\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            if res.get("international_format") or res.get("raw_format"):\n'
    '                phone = res.get("international_format") or res.get("raw_format")\n'
    '                break\n'
    '    except Exception:\n'
    '        pass\n'
    '    if phone:\n'
    '        context.transition_to("Build Callback Payload")\n'
    '    else:\n'
    '        context.transition_to("BetterContact mobile (30cr)")\n'
    '    return {"prospeo_phone": phone}',
    "If Prospeo found a mobile, build payload. Else last resort."
)

better_mobile = tool_node(
    "BetterContact mobile (30cr)", "bettercontact-find-mobile-phone", PKG_BETTER,
    {"social_url": {"type": "reference", "expression": "{{linkedin_url}}"},
     "name": {"type": "reference", "expression": "{{full_name}}"},
     "company": {"type": "reference", "expression": "{{company_name}}"},
     "domain": {"type": "reference", "expression": "{{company_domain}}"}},
    "BetterContact mobile (30cr, last resort)."
)

gate_better = cond_node(
    "BetterContact found?",
    'def handler(context):\n'
    '    phone = ""\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            data = res.get("data") or []\n'
    '            if isinstance(data, list) and data:\n'
    '                p = data[0].get("contact_phone_number") or ""\n'
    '                if p:\n'
    '                    phone = p\n'
    '                    break\n'
    '    except Exception:\n'
    '        pass\n'
    '    context.transition_to("Build Callback Payload")\n'
    '    return {"better_phone": phone}',
    "Last mobile source. Build payload regardless."
)

# ============ OUTPUT ============

output_node = code_node(
    "Build Callback Payload",
    'def handler(context):\n'
    '    row = context.get_input("row") or ""\n'
    '    first = context.get_input("first_name") or ""\n'
    '    last = context.get_input("last_name") or ""\n'
    '    full = context.get_input("full_name") or ""\n'
    '    company = context.get_input("company_name") or ""\n'
    '    domain = context.get_input("company_domain") or ""\n'
    '    title = context.get_input("job_title") or ""\n'
    '    linkedin = context.get_input("linkedin_url") or ""\n'
    '    email = (context.get_input("email") or "").strip()\n'
    '    phone = ""\n'
    '    email_source = "input" if email else ""\n'
    '    phone_source = ""\n'
    '    try:\n'
    '        branch = context.get_input("_branchOutputs") or {}\n'
    '        for node_id, out in branch.items():\n'
    '            res = (out or {}).get("result") or {}\n'
    '            # email\n'
    '            if not email and res.get("email"):\n'
    '                email = res["email"]\n'
    '                email_source = "clay_email"\n'
    '            # phone: lyne\n'
    '            if not phone and res.get("mobile_phone"):\n'
    '                phone = res["mobile_phone"]\n'
    '                phone_source = "lyne"\n'
    '            # phone: wiza\n'
    '            data = res.get("data") or {}\n'
    '            if isinstance(data, dict):\n'
    '                if not phone and (data.get("mobile_phone") or data.get("phone_number")):\n'
    '                    phone = data.get("mobile_phone") or data.get("phone_number")\n'
    '                    phone_source = "wiza"\n'
    '            # phone: findymail\n'
    '            if not phone and res.get("mobilePhone"):\n'
    '                phone = res["mobilePhone"]\n'
    '                phone_source = "findymail"\n'
    '            # phone: prospeo\n'
    '            if not phone and (res.get("international_format") or res.get("raw_format")):\n'
    '                phone = res.get("international_format") or res.get("raw_format")\n'
    '                phone_source = "prospeo"\n'
    '            # phone: bettercontact\n'
    '            if not phone and isinstance(res.get("data"), list) and res["data"]:\n'
    '                p = res["data"][0].get("contact_phone_number") or ""\n'
    '                if p:\n'
    '                    phone = p\n'
    '                    phone_source = "bettercontact"\n'
    '    except Exception:\n'
    '        pass\n'
    '    return {\n'
    '        "row": row, "first_name": first, "last_name": last,\n'
    '        "full_name": full, "company_name": company,\n'
    '        "company_domain": domain, "job_title": title,\n'
    '        "linkedin_url": linkedin, "email": email,\n'
    '        "mobile_phone": phone, "email_source": email_source,\n'
    '        "phone_source": phone_source, "enriched": True,\n'
    '    }',
    "Assembles the final enriched record from all branch outputs."
)

# Creation order: targets before sources
NODES = [
    output_node,
    gate_better, better_mobile,
    gate_prospeo, prospeo_mobile,
    gate_findymail, findymail_mobile,
    gate_wiza, wiza_mobile,
    gate_lyne, lyne_mobile,
    gate_datagma_email, datagma_email,
    gate_findymail_email, findymail_email,
    gate_leadmagic_email, leadmagic_email,
    gate_need_email,
]

EDGES = [
    ("Need email?", "LeadMagic email (1cr)"),
    ("Need email?", "Lyne mobile (4cr)"),
    ("LeadMagic email (1cr)", "LeadMagic email found?"),
    ("LeadMagic email found?", "Lyne mobile (4cr)"),
    ("LeadMagic email found?", "Findymail email (2cr)"),
    ("Findymail email (2cr)", "Findymail email found?"),
    ("Findymail email found?", "Lyne mobile (4cr)"),
    ("Findymail email found?", "Datagma email (2cr)"),
    ("Datagma email (2cr)", "Datagma email found?"),
    ("Datagma email found?", "Lyne mobile (4cr)"),
    ("Lyne mobile (4cr)", "Lyne found?"),
    ("Lyne found?", "Build Callback Payload"),
    ("Lyne found?", "Wiza mobile (7cr)"),
    ("Wiza mobile (7cr)", "Wiza found?"),
    ("Wiza found?", "Build Callback Payload"),
    ("Wiza found?", "Findymail mobile (9cr)"),
    ("Findymail mobile (9cr)", "Findymail found?"),
    ("Findymail found?", "Build Callback Payload"),
    ("Findymail found?", "Prospeo mobile (10cr)"),
    ("Prospeo mobile (10cr)", "Prospeo found?"),
    ("Prospeo found?", "Build Callback Payload"),
    ("Prospeo found?", "BetterContact mobile (30cr)"),
    ("BetterContact mobile (30cr)", "BetterContact found?"),
    ("BetterContact found?", "Build Callback Payload"),
]

def main():
    name = "Cadence Contact Enrichment (Email + Mobile)"
    wf = cli("workflows", "create", "--name", name)
    wfid = wf["id"]
    print(f"created workflow {wfid}")

    created = {}
    for node in NODES:
        res = cli("workflows", "nodes", "create", wfid, "--input", json.dumps(node))
        created[node["name"]] = res["nodeId"]
        print(f"  created {node['name']} -> {res['nodeId']}")

    from collections import defaultdict
    target_edges = defaultdict(list)
    for src, tgt in EDGES:
        target_edges[tgt].append({"sourceNode": created[src]})
    for tgt, edges in target_edges.items():
        cli("workflows", "nodes", "update", wfid, created[tgt], "--input",
            json.dumps({"incomingEdges": edges}))
        print(f"  wired -> {tgt}")

    # Webhook trigger
    trig = cli("workflows", "triggers", "create", wfid, "--input", json.dumps({
        "triggerType": "webhook",
        "inputSchema": {"type": "object", "properties": {
            "row": {"type": "string"},
            "first_name": {"type": "string"}, "last_name": {"type": "string"},
            "full_name": {"type": "string"},
            "company_name": {"type": "string"}, "company_domain": {"type": "string"},
            "job_title": {"type": "string"}, "linkedin_url": {"type": "string"},
            "email": {"type": "string"}}}}))
    trig_id = trig["resourceId"]
    trig_node = cli("workflows", "triggers", "get", trig_id)["workflowNodeId"]
    cli("workflows", "nodes", "update", wfid, created["Need email?"],
        "--input", json.dumps({"incomingEdges": [{"sourceNode": trig_node}]}))
    print(f"  wired trigger -> Need email?")

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
