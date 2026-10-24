# Forecast Skill — AE Weekly Call (PERMANENT)

Phase 3 of the weekly forecast tracker: the GTM agent collects each AE's weekly forecast call in Slack DM and appends it to the Forecast Log. Spec source: forecast spec §6 (conversation), §4.3 (Forecast Log schema). This playbook covers **AEs only**; VP ({{AE_1}}) and CRO ({{SALES_LEADER}}) skills are separate phases.

- **Script:** `scripts/forecast-skill/AE_forecast_skill.py` — all date math, identity, parsing, last-call lookup, and the sheet append. Run it; never hand-compute weeks or hand-write rows. (AE-specific; VP/CRO get their own role-based skills.)
- **Sheet:** live tracker `REDACTED_GOOGLE_ID`, tab `Forecast Log`, columns A–K (append-only).
- **Who submits:** roster Role = AE in `Quarter Reference!A31:F40`. Currently {{AE_6}}, {{AE_4}}, {{AE_3}}, {{SDR_1}}.

## The opener (Thursday cron)

One isolated cron (`forecast-opener-aes`) fires Thursday 7:00 AM PT. It runs `roster-openers`, which prints every roster AE's opener text as JSON (the Role column in Quarter Reference decides who's included — roster changes need no cron changes), and sends each AE their DM. The opener already contains the week line and the previous-call echo, so the DM is both the reminder and the AE's visibility into what they forecasted last week.

## Conversation flow (when an AE replies)

**Default: single-message entry (rule from {{REVOPS_1}}, 2026-10-05).** Ask for everything in one question. Fall back to one-question-at-a-time only if the AE asks for it or the combined parse fails.

Identify who you're talking to at the start:

1. **Resolve identity:** `resolve --slack-id <their Slack ID>`. If `ok:false`, tell them they're not on the forecast roster and stop. Confirm role is AE (if VP/CRO, this playbook doesn't apply — phase 2/3).
2. **Week line:** state the week — run `week` (no args = today PT) and say: "This is your call for the forecast week of Tue Oct 6 – Mon Oct 12, Q4 FY26." (The opener already said it; restate only if the conversation has moved on.)
3. **The one ask:** "In the following order enter your weekly Commit $, Best Case $, Pipeline $. Add your Current state and Notes (more detailed info)."
   - Commit = Closed Won this quarter + anything open in Commit. Best Case = Closed Won + Commit + open Best Case. Pipeline = Closed Won + Commit + Best Case + all remaining open pipeline. Define only if they ask.
   - They can answer in any format — "120k 200k 490k current state: 2 deals in redlines notes: Matson MSA due tmrw" is fine.
4. **Parse:** run `parse-call --input "<their full reply>"`. It returns `{commit, best_case, pipeline, current_state, notes}`.
   - First three dollar amounts in text order = Commit, Best Case, Pipeline. Text after `current state:` / `notes:` markers splits into those fields; no markers → remaining text goes to Notes, Current State stays blank.
   - If `ok:false` (fewer than 3 amounts found), show the error and ask them to re-enter just the three numbers — never guess a missing category.
8. **Completeness reminder (rule from {{REVOPS_1}}, 2026-10-02):** before the summary, check all five fields are answered. If any field was skipped or left blank (Current State or Notes), remind them: "Heads up — you left Current State blank. Want to add it? If not, I'll log it as 'Nothing was added.'" Re-ask once. If they confirm leaving it blank, log the literal text `Nothing was added` in that field — never write an empty cell. If Notes was skipped entirely, go back and ask it — Notes is never blank without an explicit answer.
9. **Summary + confirm (HARD GATE — always, rule from {{REVOPS_1}} 2026-10-05):** show all five parsed answers in a summary, ask them to confirm or change any one. Only write after an explicit confirm. Never append off a bare parse without confirmation.
10. **Write:** `append --name "<Name>" --commit N --best-case N --pipeline N [--notes T] [--current-state T]`.
11. **Confirm:** "Logged for the forecast week of Oct 6–12. If you resubmit this week, the latest one counts."

## Zero values (rule from {{REVOPS_1}}, 2026-10-05)

`$0` is a real call. If any category is zero, it logs as `$0` in the sheet — never "-", never a blank cell. The Forecast Log number format (columns G–I) is pinned to `$#,##0;-$#,##0;$0` so zeros always render as `$0`. Don't treat a `$0` answer as "no answer" for the completeness reminder — it's complete.

## Number handling

For combined replies use `parse-call --input "<full text>"` (step 4). For a bare dollar answer (when a conversation does go one-at-a-time), parse through `parse --input "<raw>"` — never convert in your head.
- Accepts: `0000000`, `120,000`, `$120K`, `120k`, `1.2M`, `0`, `none` (= 0).
- Rejects negatives (script errors) — tell them no negative numbers.
- No cross-field validation. Commit, Best Case, and Pipeline are independent numbers — the seller and their leader own the relationship between them.

## Writing rules (hard)

- The script appends exactly one row, columns A–K, with RAW serial dates and whole-dollar numbers. Never edit or delete existing rows — a resubmission is a new row; the sheet's latest-Submitted-At logic picks the winner.
- Take the confirm moment as the timestamp. If the conversation runs past Monday midnight PT, the confirm time decides the week — tell them the week again in the confirmation.
- If the append returns `ok:false`, tell the person it didn't save, and alert {{REVOPS_1}}. Never claim success on a failed write.
- `FORECAST_SHEET_ID` env var points the script at a scratch copy for testing — never test appends against the live tracker.

## Failure modes

- Write fails → tell AE, alert {{REVOPS_1}}, no success claim.
- AE not on roster → say so, stop.
- AE asks to see history → run `last --name "<Name>"` and share their own latest row only. Never share another person's calls.

## Review requests (who sees what — rule from {{REVOPS_1}}, 2026-10-02)

When someone asks to review forecast calls in the weekly sheet:
- **AE** → run `last --name "<Name>"` in `AE_forecast_skill.py` and show their own latest row only.
- **VP ({{AE_1}})** → run `team` in `VP_forecast_skill.py` — returns each AE's latest call for the current week, who hasn't submitted, and the AE roll-up totals.
- **CRO ({{SALES_LEADER}})** → run `team` in `CRO_forecast_skill.py` — returns the VP team-level call plus each AE's latest call and roll-up totals.

## Self-serve entry (AE initiates, any day)

The Thursday opener is a prompt, not the only door. An AE can start or change their forecast any time by DMing the GTM agent — "forecast", "change my forecast", "I was out Thursday", etc. The flow is identical to the opener path:

1. Resolve identity (`resolve --slack-id`).
2. Run the same single-question conversation: "In the following order enter your weekly Commit $, Best Case $, Pipeline $. Add your Current state and Notes (more detailed info)."
3. `parse-call` their reply, show the summary, get an explicit confirm, then `append` a new row.

Because the log is append-only and the sheet uses latest Submitted At per person per week, a resubmission on any day (Tuesday through Monday) simply becomes that week's call. An AE who was out Thursday can submit Friday, Monday, or even Tuesday (which lands in the *new* week). No special command, no sheet access — they just message the GTM agent.
