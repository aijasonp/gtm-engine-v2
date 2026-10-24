#!/usr/bin/env python3
"""Enrich the GTM agent sheet (REDACTED_GOOGLE_ID) via Floqer.

Reuses the existing cost-optimized workflow "Houston Contact Enrichment"
(00000000-0000-0000-0000-000000000000):
  Find LinkedIn URL (email) -> Find Phone (waterfall Floqer->prospeo->Wiza->leadmagic->findymail)
  -> Enrich phone+email (person_enrich_by_floqer)

Only enriches rows missing phone (and the single missing-email row). Writes
results back to the sheet via batchUpdate, only filling gaps (never overwrite).
"""
import json, os, sys, time, urllib.request, urllib.error

API = "https://api.floqer.com/api/v1"
WF = "00000000-0000-0000-0000-000000000000"
SHEET = WF  # main sheet id == workflow id
KEY = os.environ["FLOQER_API_KEY"]
SPREADSHEET = "REDACTED_GOOGLE_ID"

def api(path, method="GET", body=None):
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {KEY}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"status": e.code, "error": e.read().decode()[:500]}

def main():
    # 1. Read sheet
    import subprocess
    out = subprocess.run(
        ["gwsg", "sheets", "+read", "--spreadsheet", SPREADSHEET,
         "--range", "Sheet1!A1:L201", "--format", "json"],
        capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    vals = d["values"]
    hdr = vals[0]
    def idx(n): return hdr.index(n) if n in hdr else None
    pi, ei = idx("Phone"), idx("Email")
    first_i, last_i, title_i, comp_i = idx("First"), idx("Last"), idx("Title"), idx("Company")

    # 2. Identify gap rows (missing phone; plus the single missing-email row)
    rows = []
    for r in vals[1:]:
        num = r[0] if r else ""
        phone = str(r[pi]).strip() if pi is not None and len(r) > pi else ""
        email = str(r[ei]).strip() if ei is not None and len(r) > ei else ""
        if not phone or not email:
            rows.append({
                "row_num": num,
                "first": r[first_i] if first_i is not None and len(r) > first_i else "",
                "last": r[last_i] if last_i is not None and len(r) > last_i else "",
                "title": r[title_i] if title_i is not None and len(r) > title_i else "",
                "company": r[comp_i] if comp_i is not None and len(r) > comp_i else "",
                "email": email,
                "phone": phone,
            })
    print(f"Gap rows to enrich: {len(rows)} (missing phone or email)")
    if not rows:
        print("Nothing to do.")
        return

    # 3. Push rows to Floqer (run_after_add=none; we'll trigger run explicitly)
    #    Idempotent: skip emails already present in the Floqer sheet.
    def list_all():
        out = []
        page = 1
        while True:
            lr = api(f"/workflows/{WF}/sheets/{SHEET}/rows/list", "POST",
                     {"page_size": 200, "page_no": page})
            if lr.get("status") != 200:
                print("rows/list err:", json.dumps(lr)[:300]); break
            rws = lr.get("data", {}).get("rows", [])
            out.extend(rws)
            if len(rws) < 200:
                break
            page += 1
        return out
    lr0 = list_all()
    existing = set()
    for r in lr0:
        em = (r.get("inputs") or {}).get("email") or ""
        if em:
            existing.add(em)
    to_add = [r for r in rows if r["email"] not in existing]
    print(f"Already in Floqer: {len(rows)-len(to_add)}; to add: {len(to_add)}")
    row_ids = []
    if to_add:
        payload = {"rows": [
            {"email": r["email"], "firstname": r["first"], "lastname": r["last"],
             "company": r["company"], "jobtitle": r["title"],
             "linkedin_url": "", "phone": r["phone"]}
            for r in to_add
        ], "run_after_add": "none"}
        res = api(f"/workflows/{WF}/sheets/{SHEET}/rows", "POST", payload)
        if res.get("status") not in (200, 201):
            print("Add rows failed:", json.dumps(res)[:800]); sys.exit(1)
        row_ids = (res.get("data") or {}).get("row_ids") or res.get("row_ids") or []
        print(f"Pushed {len(to_add)} rows. row_ids: {len(row_ids)}")

    # 4. Run ONLY the new rows (not run-all, which re-bills everything)
    if not row_ids:
        # all already present -> run the ones matching our gap emails
        emails = {r["email"] for r in rows}
        row_ids = [r.get("row_id") for r in lr0
                   if (r.get("inputs") or {}).get("email") in emails]
        print(f"Reusing existing rows; targeting {len(row_ids)} row_ids")
    run = api(f"/workflows/{WF}/sheets/{SHEET}/run", "POST", {"row_ids": row_ids})
    print("Run trigger:", json.dumps(run)[:400])

    # 5. Poll rows/list until MY rows complete (filter by row_ids)
    target = set(row_ids)
    for _ in range(90):
        time.sleep(10)
        lr = list_all()
        mine = [r for r in lr if r.get("row_id") in target]
        statuses = {r.get("row_status") for r in mine}
        print(f"  poll: {len(mine)}/{len(target)} mine, statuses={statuses}")
        if statuses and statuses <= {"complete", "has_failures"} and len(mine) >= len(target):
            break
    else:
        print("Timed out polling"); sys.exit(1)
    rws = [r for r in lr if r.get("row_id") in target]

    # 6. Extract enriched values keyed by input email
    enriched = {}
    for r in rws:
        inputs = r.get("inputs", {})
        email = inputs.get("email", "")
        outs = r.get("outputs", {})
        # person_enrich_by_floqer outputs
        pe = outs.get("person_enrich_by_floqer_01lq", {}) or {}
        wf = outs.get("personal_phone_number_by_linkedin_url_waterfall_01gg", {}) or {}
        li = outs.get("person_linkedin_url_by_email_01xs", {}) or {}
        enriched[email] = {
            "phone": pe.get("phone_number") or wf.get("phone_number") or "",
            "email": pe.get("professional_email") or email,
            "linkedin": li.get("linkedin_url") or "",
            "status": r.get("row_status"),
        }

    # 7. Build sheet updates (only fill gaps)
    updates = []
    for r in rows:
        e = enriched.get(r["email"])
        if not e:
            continue
        # find sheet row index (1-based data row = header row 1 + index)
        # match by row_num
        for i, sr in enumerate(vals[1:], start=2):
            if sr and sr[0] == r["row_num"]:
                if not r["phone"] and e["phone"]:
                    updates.append({"range": f"Sheet1!K{i}", "values": [[e["phone"]]]})
                if not r["email"] and e["email"] and e["email"] != r["email"]:
                    updates.append({"range": f"Sheet1!L{i}", "values": [[e["email"]]]})
                break

    print(f"Sheet updates to apply: {len(updates)}")
    if updates:
        # batchUpdate via gwsg
        with open("/tmp/gtm_agent_updates.json", "w") as f:
            json.dump({"valueInputOption": "USER_ENTERED", "data": updates}, f)
        subprocess.run(
            ["gwsg", "sheets", "batchUpdate", "--spreadsheet", SPREADSHEET,
             "--body", "/tmp/gtm_agent_updates.json"],
            check=True)
        print("Wrote back to sheet.")

    # 8. Summary
    filled_phone = sum(1 for r in rows if not r["phone"] and enriched.get(r["email"], {}).get("phone"))
    print(f"\nSUMMARY: {len(rows)} gap rows processed. Phone filled: {filled_phone}.")
    for r in rows:
        e = enriched.get(r["email"])
        if e and e["phone"]:
            print(f"  {r['first']} {r['last']} ({r['company']}) -> {e['phone']}")

if __name__ == "__main__":
    main()
