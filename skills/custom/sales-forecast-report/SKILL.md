---
name: sales-forecast-report
description: Generate a weekly sales forecast report as visually stunning HTML with embedded charts, per-rep scorecards, AI deal analysis, confidence scores, next steps, and weekly action items. Pulls live data from HubSpot. Use when asked to "generate the weekly report", "run the sales forecast", "create the pipeline report", "show me the forecast", "weekly sales report", or any request for a sales, pipeline or forecast report.
---

# Sales Forecast Report

Generates a complete weekly sales forecast report from HubSpot data. Output is a branded HTML file uploaded to Google Drive.

## Workflow

### Step 1: Pull HubSpot Data

Run the data pull script:
```bash
cd <skill library>/skills/sales-forecast-report
python3 scripts/pull_deals.py > /tmp/sf_data.json
```

This outputs a JSON file with all open deals, engagement history, rep stats, and stage metadata. Inspect for errors before continuing.

### Step 2: Analyze Each Deal

Read `/tmp/sf_data.json`. For each open deal, produce:

**Confidence Score (0-100):**
- Start at 60 (baseline for any open deal in a valid stage)
- See `references/confidence-scoring.md` for the full scoring rubric

**Next Steps:**
- Read the deal's most recent engagement (email, call, meeting note) and last deal note
- Infer what the logical next action is based on stage and last activity
- Be specific: not "follow up" but "Send security team evaluation framework per Alexis' request from 3/14 call"

**What Must Happen This Week:**
- Based on close date proximity, deal risk flags, and current stage
- Prioritize: deals closing this week > deals at risk > high-value stalled deals
- One clear, actionable sentence per deal

**Hygiene Flags:**
- Apply the criteria in `references/hygiene-criteria.md`
- Each deal gets a list of flags (empty list = clean)

Compile results into a structured dict: `{ deal_id: { confidence, next_steps, weekly_action, hygiene_flags } }`

### Step 3: Generate the Report

Run:
```bash
python3 scripts/render_report.py \
  --data /tmp/sf_data.json \
  --analysis /tmp/sf_analysis.json \
  --output /tmp/sales-report-$(date +%Y-%m-%d).html
```

The renderer produces a self-contained HTML file with embedded CSS and Chart.js charts.

### Step 4: Upload to Drive Archive Folder

The archive folder is set per deployment in `REPORTS_FOLDER_ID` (Google Drive folder ID). Share targets are in `REPORT_SHARE_WITH` (comma-separated emails).

Upload uses a two-step process (gwsg does not support inline HTML→Google Doc conversion):

```bash
WEEK_DATE=$(date +%Y-%m-%d)
REPORT_NAME="${REPORT_COMPANY:+$REPORT_COMPANY }Sales Forecast: Week of $WEEK_DATE"
FOLDER_ID="$REPORTS_FOLDER_ID"

# Step 4a: Upload HTML file to Drive folder
HTML_FILE_ID=$(gwsg drive files create \
  --json "{\"name\": \"${REPORT_NAME} [source]\", \"parents\": [\"${FOLDER_ID}\"]}" \
  --upload "/tmp/sales-report-${WEEK_DATE}.html" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# Step 4b: Copy-convert to native Google Doc format (triggers HTML→Docs conversion)
DOC_ID=$(gwsg drive files copy \
  --params "{\"fileId\": \"${HTML_FILE_ID}\"}" \
  --json "{\"name\": \"${REPORT_NAME}\", \"mimeType\": \"application/vnd.google-apps.document\", \"parents\": [\"${FOLDER_ID}\"]}" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# Step 4c: Delete the HTML source file
gwsg drive files delete --params "{\"fileId\": \"${HTML_FILE_ID}\"}" 2>/dev/null

# Step 4d: Share with each address in REPORT_SHARE_WITH
for EMAIL in ${REPORT_SHARE_WITH//,/ }; do
  gwsg drive permissions create \
    --params "{\"fileId\": \"${DOC_ID}\"}" \
    --json "{\"type\": \"user\", \"role\": \"writer\", \"emailAddress\": \"${EMAIL}\"}" 2>/dev/null
done

echo "Google Doc: https://docs.google.com/document/d/${DOC_ID}/edit"
```

Post the direct Google Doc link + the folder link.

### Step 5: Post Summary to Slack

After posting the link, send a brief summary to the forecast channel with:
- Total open pipeline $ 
- Number of deals closing this week
- Top 2-3 hygiene issues
- Link to the full report

---

## Report Sections (in order)

See `references/report-structure.md` for full layout specifications.

1. **Header**: company logo (`REPORT_LOGO`), report title, week date, total pipeline $, and a 3-number summary (deals in pipeline, closing this week, at-risk count)
2. **Executive Summary**: 4 stat cards: total pipeline $, weighted forecast, deals closing this week, hygiene score (% of deals clean)
3. **Pipeline Funnel**: Bar/funnel chart by stage: deal count and $ value. Week-over-week delta.
4. **Forecast Hygiene**: Table of flagged deals with flag type, rep, amount, days since last activity
5. **Per-Rep Scorecards**: One card per rep: pipeline $, deal count, weighted forecast, activity score, win rate (if available), top deal
6. **Deal Analysis**: Full deal table: one row per deal with stage, amount, close date, confidence score (color-coded), next steps, weekly action, hygiene flags
7. **Weekly Priorities**: Consolidated action list across all deals, sorted by urgency

---

## Data Sources

- **HubSpot** (primary): All open deals, deal properties, engagement history (emails, calls, meetings, notes), contacts, companies
- **HubSpot owner mapping**: maps owner IDs to rep names from the live owners API
- **Current date**: Used for hygiene calculations and weekly date label

## Notes

- Reps: every active HubSpot owner with open deals, plus unassigned deals
- HubSpot token: `$HUBSPOT_TOKEN` from env or `GTM_ENV_FILE`
- Branding: `REPORT_COMPANY`, `REPORT_LOGO`, `REPORT_ACCENT`
- Extra stages to exclude: `EXCLUDED_DEAL_STAGES` (comma-separated stage IDs)
- All $ amounts in USD
- Confidence scores: 0-39 = red, 40-69 = yellow, 70-100 = green
- Hygiene score = (clean deals / total deals) × 100, shown as % with color coding

For scoring rubric: see `references/confidence-scoring.md`
For hygiene criteria: see `references/hygiene-criteria.md`
For full HTML layout spec: see `references/report-structure.md`
