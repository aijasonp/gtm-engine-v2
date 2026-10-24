---
name: icp-learner
description: Analyze HubSpot win/loss data to surface ICP recommendations whenever someone asks for ICP insights, deal pattern analysis, or HubSpot closed-won vs closed-lost breakdowns.
---

# ICP Learning Analyzer

## Overview
This skill pulls the latest closed-won and closed-lost deals from HubSpot, enriches them with company metadata, and produces statistical win-rate views plus an ICP Recommendation Card.

## Step 1: Verify HubSpot credentials
1. Confirm `HUBSPOT_TOKEN` (or compatible PAT) is exported or stored in the env file (`GTM_ENV_FILE`, default `~/.gtm/.env`).
2. If missing, retrieve the token via the approved secret channel before running the tool.

## Step 2: Run the analyzer
From the workspace root:
```bash
cd <path to the skill library>
python skills/icp-learner/icp_learner.py [--summary] [--days 365]
```
- No flags: full analysis + ICP card
- `--summary`: output only the ICP card
- `--days N`: limit deals to those closed within the last N days

## Step 3: Review outputs
- Human-readable results stream to stdout (win rates by industry, company size, deal size, loss reasons, average deal sizes, ICP narrative).
- A JSON artifact saves to `skills/icp-learner/outputs/icp-analysis-YYYY-MM-DD.json` containing the metrics, card, and filters used.

## Error Handling
- **Missing token:** Script exits with an explicit message instructing you to set `HUBSPOT_TOKEN`.
- **HubSpot HTTP errors:** You’ll see the HTTP status + payload. Fix the token/permissions or retry if it’s a transient 5xx.
- **Empty dataset:** The tool reports `No closed deals found for the selected window` and exits cleanly.

## Examples
1. **Full lookback:** `python skills/icp-learner/icp_learner.py`
2. **Year-to-date summary card:** `python skills/icp-learner/icp_learner.py --summary --days 365`

Use the JSON artifact to drop metrics into slides, or paste the Markdown ICP card into Slack/Notion updates.
