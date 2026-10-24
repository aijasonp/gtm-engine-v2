---
name: forecast-call
description: Collect each AE's weekly forecast call (Commit, Best case, Pipeline) in a Slack DM, log it append-only, and build the weekly roll-up for sales leadership. Use when the weekly forecast reminder fires, when an AE types "forecast", or when a leader asks for the team forecast or who has not submitted.
metadata:
  version: 1.0.0
---

# Forecast Call

Collect one forecast call per AE per week, keep every submission, and give leadership a clean roll-up. Numbers are entered by people. You collect, validate, store and summarize. You never forecast for an AE.

## Schedule (set as reminders on the RevOps instance)

| When | What |
| --- | --- |
| Wednesday 9:00 local | DM each AE: forecast call due Thursday, their open deal count and total amount for the quarter |
| Thursday 8:00 local | DM each AE the opener: quarter, open deals, total amount, quarterly goal, "type forecast to start" |
| Thursday 16:00 local | One nudge to AEs with no submission this week |
| Friday 8:00 local | Roll-up DM to each recipient in the forecast config |
| Any time | An AE types `forecast` in a DM and the same flow starts |

## The conversation

Default: ask for all three numbers in one message. Fall back to one question at a time only if the AE asks or the combined answer does not parse.

1. **Commit**: deals the AE is 80%+ confident close this quarter. PO in hand, a partner bringing the deal for certain, or paper in final signature.
2. **Best case**: Commit plus every deal at 25% to under 80% confidence this quarter. Must be greater than or equal to Commit.
3. **Pipeline**: deals dated this quarter under 25% confidence that could still close. Separate from Best case, not cumulative. Total open = Best case + Pipeline.

Then one optional note ("skip" to skip).

### Validation
- Missing, ambiguous or unparseable value: re-ask only that value.
- Best case below Commit: re-ask only Best case.
- Zero is a valid answer. Confirm it once ("Commit is $0 this week, right?") and accept it.
- Before the summary, check all fields. If the note was skipped, that is fine; if a number is blank, ask for it.

### Confirm before writing (hard gate)
Show the three numbers, Total open, change vs last week for each (▲ up, ▼ down, – no change), and coverage vs goal. Ask the AE to confirm or change one value. Write only after an explicit confirm.

After writing, show the AE their open deals dated this quarter, earliest close date first: deal name (linked to the CRM), last activity date, one-line latest update, and a "No update logged" flag where it applies. Do not ask the AE to fix anything.

## Storage rules
- **Append-only.** Never overwrite a prior row. A second submission in the same week adds a row; the latest one counts as that week's call.
- One row: week-of (Monday date), AE, commit, best case, pipeline, total open, note, submitted at (UTC).
- Write to the forecast log tool configured for this deployment (sheet or table). If the write fails, tell the AE it did not save, alert the RevOps owner, and never claim success.
- CRM unavailable: still collect and record the call, and note the gap in the roll-up.

## Privacy
- An AE sees only their own calls.
- A manager sees their roster's latest calls and roll-up totals.
- A sales leader sees every AE's latest call plus the team roll-up.
- Recipients and roles come from the forecast config, never from memory.

## Friday roll-up
For each recipient in scope:
- Team totals: Commit, Best case, Pipeline, Total open, each with week-over-week change
- Each AE's latest call, coverage vs goal
- Who has not submitted this week
- Red flags: deals with no activity in 30+ days, deals pushed 5+ times, deals dated in quarter with no forecast category

## Quarter math
Use the fiscal calendar in the deployment config. If none is set, quarter = calendar quarter. Week of = the Monday of the submission week.

## Test mode
When test mode is on, message only the recipients listed in the forecast config. Never message AEs in test mode.
