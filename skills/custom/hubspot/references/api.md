# HubSpot API Reference

This file summarizes the HubSpot endpoints and behaviors relied on by the `hubspot` skill. Load it when you need endpoint details, rate limits, or property guidance.

## Authentication

- **Token**: personal access token (PAT) stored as `HUBSPOT_TOKEN` in the env file (`GTM_ENV_FILE`, default `~/.gtm/.env`).
- Export `HUBSPOT_API_TOKEN` before running scripts:
  ```bash
  export HUBSPOT_API_TOKEN=$(grep ^HUBSPOT_TOKEN ${GTM_ENV_FILE:-~/.gtm/.env} | cut -d'=' -f2-)
  ```
- All requests use `Authorization: Bearer <token>` + `Content-Type: application/json`.

## Core REST endpoints

| Capability | Endpoint | Notes |
|------------|----------|-------|
| Search companies | `POST /crm/v3/objects/companies/search` | Accepts `filterGroups`. Use `CONTAINS_TOKEN` on `name` or `domain`. Limit ≤ 100 per call. |
| Search deals | `POST /crm/v3/objects/deals/search` | Same pattern as companies. Add `properties` array for fields to return. |
| Batch read objects | `POST /crm/v3/objects/{type}/batch/read` | Up to 100 IDs per batch. Types: `companies`, `deals`, `contacts`, `notes`, etc. |
| Associations | `GET /crm/v3/objects/{from}/{id}/associations/{to}` | Paginate with `limit` + `after`. Use to hop company→deal, deal→contact, etc. |
| Pipelines + deal stages | `GET /crm/v3/pipelines/deals` | Returns all pipelines, each with stage IDs, labels, and order. |
| Legacy engagements | `GET /engagements/v1/engagements/associated/deal/{deal_id}/paged` | Primary source for activities (notes/calls/meetings/emails). Paginate via `offset`. |

## Property cheatsheet

### Company properties pulled
- `name`, `domain`, `industry`, `description`
- `city`, `country`, `numberofemployees`
- `createdate`, `hs_lastmodifieddate`

### Deal properties pulled
- Core: `dealname`, `amount`, `pipeline`, `dealstage`, `createdate`, `closedate`
- Status flags: `hs_is_closed`, `hs_is_closed_won`
- Context: `description`, `next_step`

### Contact properties pulled
- `firstname`, `lastname`, `jobtitle`
- `email`, `phone`, `company`
- `hs_lastmodifieddate`

### Engagement metadata
- **Notes**: `metadata.body`
- **Meetings**: `metadata.title`, `metadata.body`
- **Calls**: `metadata.title`, `metadata.body`, `metadata.hs_call_body`
- **Emails**: `metadata.subject`, `metadata.text` (often redacted without extra scopes)

## Rate limits + retry strategy

HubSpot applies burst + daily limits per app + per account. Practical guidance:

- 4 requests/second per token is usually safe. The scripts already back off when 429/5xx appear.
- Exponential backoff: sleep `2^attempt` seconds (capped at 20s) on 429, 500, 502, 503, 504.
- The legacy engagements API occasionally returns empty pages before `hasMore=false`; keep paginating until both `hasMore` and `offset` clear.

## Pipelines & stages

Use `/crm/v3/pipelines/deals` to map stage IDs to human-readable names. Example JSON fragment:

```json
{
  "results": [
    {
      "pipelineId": "default",
      "label": "Sales Pipeline",
      "stages": [
        {"stageId": "appointmentscheduled", "label": "Appointment Scheduled", "displayOrder": 0},
        {"stageId": "qualifiedtobuy", "label": "Qualified to Buy", "displayOrder": 1},
        {"stageId": "presentationscheduled", "label": "Presentation Scheduled", "displayOrder": 2},
        {"stageId": "decisionmakerboughtin", "label": "Decision Maker Bought-In", "displayOrder": 3},
        {"stageId": "contractsent", "label": "Contract Sent", "displayOrder": 4},
        {"stageId": "closedwon", "label": "Closed Won", "displayOrder": 5},
        {"stageId": "closedlost", "label": "Closed Lost", "displayOrder": 6}
      ]
    }
  ]
}
```

When summarizing deals, convert `pipeline`+`dealstage` using this lookup for clarity.

## Engagement best practices

1. Pull engagements via the legacy v1 API for each deal; it captures notes/calls/meetings created via the classic CRM UI.
2. Each record includes `engagement.type` (NOTE, MEETING, CALL, EMAIL, TASK, etc.) and `metadata` with the body/title.
3. Associations provide `contactIds`, `companyIds`, `dealIds`. Use them to backfill contacts missed by primary associations.
4. HubSpot redacts most email bodies unless the PAT has `crm.objects.emails.read`. Expect blank `metadata.text` for many emails.

## General lookup workflow

1. Search by company name (CONTAINS_TOKEN). Keep top candidates in the output for manual inspection.
2. Resolve to best match (exact name/domain matching with fallbacks).
3. Pull company→deal associations. Supplement with deal search by name for free-text matches.
4. For each deal, pull contacts + engagements + additional associated companies.
5. Batch-read contacts/companies to hydrate properties.
6. Feed the resulting JSON into `scripts/render_hubspot_summary.py` to create a readable brief.
