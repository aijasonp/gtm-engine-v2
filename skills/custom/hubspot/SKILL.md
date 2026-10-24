---
name: hubspot
description: HubSpot CRM account research for GTM agents. Use when you need to search/read companies, deals, contacts, or pull engagement history, list pipelines/stages, or generate named-account summaries from HubSpot data.
---

# HubSpot Skill

## Overview
Use this skill to answer HubSpot CRM questions without reopening the UI. It bundles:
- **Data pull automation** (`scripts/pull_hubspot.py`) that searches companies, hydrates deals + contacts, and captures engagement history via the legacy v1 API.
- **Summary rendering** (`scripts/render_hubspot_summary.py`) that turns the raw JSON into a readable brief (use cases, contacts, activities).
- **API reference** (`references/api.md`) covering endpoints, authentication, rate limits, and pipeline metadata.

## Quick start
1. **Prep auth**
   ```bash
   export HUBSPOT_API_TOKEN=$(grep ^HUBSPOT_TOKEN ${GTM_ENV_FILE:-~/.gtm/.env} | cut -d'=' -f2-)
   ```
2. **Pull CRM data**
   ```bash
   python scripts/pull_hubspot.py --out /tmp/hubspot.json "Northwind Logistics" "Contoso Data"
   ```
3. **Render the summary**
   ```bash
   python scripts/render_hubspot_summary.py --in /tmp/hubspot.json --out /tmp/hubspot.txt --only "Northwind Logistics"
   cat /tmp/hubspot.txt
   ```

## Core workflows

### 1. Investigate a specific account
1. Run `scripts/pull_hubspot.py` with one or more company keywords.
2. Inspect the JSON quickly (`jq '.companies[0].resolved' /tmp/hubspot.json`) if you need the raw objects.
3. Render text for stakeholders with `scripts/render_hubspot_summary.py`. Use `--only` to focus on one account, `--max-notes` or `--max-contacts` to tune verbosity.
4. Share the rendered text or quote specific snippets (deal list, use-case notes, meeting titles).

### 2. Pipeline & stage lookups
- The pull script caches `/crm/v3/pipelines/deals` at `payload["pipelines"]`. Use that to translate HubSpot `dealstage` IDs to labels when writing briefs or syncing with Salesforce.
- If you need the canonical list, open `references/api.md` (Pipelines section) or re-run the API call:
  ```bash
  python - <<'PY'
  import json
  from pathlib import Path
  data = json.load(Path('/tmp/hubspot.json').open())
  print(json.dumps(data['pipelines'], indent=2))
  PY
  ```

### 3. Engagement deep dives
- Engagements live under `entry["data"]["engagements_v1"]` grouped by deal ID.
- `render_hubspot_summary.py` already pulls out the newest notes, meetings, calls, and emails. If you need raw bodies (e.g., to grep for a keyword) run:
  ```bash
  jq -r '.companies[] | select(.query=="Northwind Logistics") | .data.engagements_v1[] | .[] | .metadata.body' /tmp/hubspot.json
  ```
- Remember: HubSpot redacts many email bodies without extra scopes; notes + meeting titles are usually the best signal.

### 4. Troubleshooting & retries
- Both scripts back off automatically on 429/5xx, but if HubSpot is flaking, re-run after a minute.
- To debug a single request, set `HUBSPOT_DEBUG=1` and rerun the pull script; it will echo endpoint failures before retrying.
- If the pull script can’t resolve a company, check the `candidates` array in the JSON to confirm naming/domain mismatches.

## Script details

| Script | Purpose | Key args |
|--------|---------|----------|
| `scripts/pull_hubspot.py` | Searches companies, aggregates deals/contacts and engagement history, records pipelines. Stdlib-only with retry logic. | `--out <file>` (required), positional company queries. |
| `scripts/render_hubspot_summary.py` | Converts pull output into a readable summary (deal highlights, contacts, activity signals). | `--in <file>` (repeatable), `--out <file>`, `--only <name>`, `--max-notes`, `--max-contacts`. |

Both scripts expect `HUBSPOT_API_TOKEN` in the environment and run fine from any directory as long as paths are correct.

## References
- `references/api.md` — endpoint list, property sets, pipeline example, retry guidance. Load it when you need detailed API behavior or stage mappings.
