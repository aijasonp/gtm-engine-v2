# gtm-engine

Reference build of an agentic GTM engine: scoring engines, signal taxonomy, outbound and forecast pipelines, eval harness, dashboard, and the skill library behind them. Private working repo and functional reference for the turnkey the GTM agent product.

All company, customer, prospect and colleague data has been removed. Placeholders mark where buyer-specific values go:

| Placeholder | Meaning |
| --- | --- |
| `{{COMPANY}}` | The selling company the engine runs for |
| `{{PRODUCT}}`, `{{MODEL}}` | That company's product or model names |
| `{{SALES_LEADER}}`, `{{AE_n}}`, `{{SDR_n}}`, `{{REVOPS_n}}`, `{{EXEC_n}}`, `{{TEAMMATE_n}}` | People, by role |
| `{{CUSTOMER_X}}`, `{{PARTNER_X}}` | Named customers and partners used as proof points |
| `{{OPS_AGENT}}`, `{{PROVISIONING_AGENT}}` | Companion agents in the original deployment |
| `REDACTED_*`, `SLACK_ID`, `0000000`, `rep@example.com`, `+1-555-010-0000` | Removed IDs, keys, emails and phone numbers |

## Layout

```
core/
  brain/          agent rules, persona, runbook, tool notes
  references/     operating specs: outbound pipeline, scoring engines, copy rules, forecast skills, feedback loop
  gtm-vault/      66-signal taxonomy with stacking and decay rules; schemas for angles, objections, language, feedback
  scripts/        outbound engine (scoring client, forecast alerts, rep feedback PRs), Clay and Floqer tooling,
                  enrichment and bounce re-enrichment, CRM cleanup, stage revision, forecast pulls, video frame audit;
                  outbound-engine scoring is product-agnostic (see product_profile.example.yaml)
skills/
  custom/         14 GTM skills written for this engine
  third-party/    open-source and community skills used alongside them (see THIRD_PARTY.md)
eval/             promptfoo regression suite, monthly eval, prompt optimization
dashboard/        Next.js GTM dashboard (synthetic sample data in src/data)
scripts/          setup helpers
```

## Setup

```bash
cp .env.example .env        # fill in your own keys; never commit .env
./scripts/install-open-source-skills.sh   # pulls the 630-skill open-source sales library
```

## Not included

Company brand and document-design assets, internal ops skills, customer and prospect records, account files, meeting briefs, event attendee lists, board and forecast documents, daily memory logs, and one-off scripts tied to specific people or events.
