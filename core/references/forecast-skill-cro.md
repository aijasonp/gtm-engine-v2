# Forecast Skill — CRO Weekly Call (PERMANENT)

Phase 3c of the weekly forecast tracker: the GTM agent collects {{SALES_LEADER}}'s (CRO) weekly team-level forecast call in Slack DM and appends it to the Forecast Log. Spec source: forecast spec §6.1 (Friday reminder, or Monday; team-level against $1M quota), §4.3 (Forecast Log schema). This playbook covers **the CRO only**; AEs and VP have their own playbooks.

- **Script:** `scripts/forecast-skill/CRO_forecast_skill.py` — all date math, identity, parsing, last-call lookup, and the sheet append. Run it; never hand-compute weeks or hand-write rows. (CRO-specific; opener includes the team-quota framing.)
- **Sheet:** live tracker `REDACTED_GOOGLE_ID`, tab `Forecast Log`, columns A–K (append-only).
- **Who submits:** {{SALES_LEADER}} (Slack SLACK_ID, HubSpot Owner ID 0000000, Role CRO, team-level quota $1,000,000).

## The opener (Friday cron)

One isolated cron (`forecast-opener-cro`) fires Friday 7:00 AM CT (America/Chicago). It runs `opener --name "{{SALES_LEADER}}"` and sends the printed text as the DM. The opener contains the week line, the previous-call echo, and the team-quota framing, so the DM is the reminder, his visibility into last week, and the scope cue all in one. A Monday submission still counts for the week that just ended (Monday is the last day of the Tue–Mon week).

## Conversation flow (when {{SALES_LEADER}} replies)

**Default: single-message entry (rule from {{REVOPS_1}}, 2026-10-05).** Ask for everything in one question. Fall back to one-question-at-a-time only if he asks for it or the combined parse fails. Same five fields as the AEs, framed as a team-level call:

1. **Resolve identity:** `resolve --slack-id SLACK_ID`. Confirm role is CRO. If resolution fails, stop.
2. **Week line:** state the week — run `week` (no args = today PT) and say: "This is your call for the forecast week of Tue Oct 6 – Mon Oct 12, Q4 FY26."
3. **The one ask:** "In the following order enter your weekly Commit $, Best Case $, Pipeline $. Add your Current state and Notes (more detailed info)."
   - Frame as team-level (his own numbers against the $1M team quota, not the AE roll-up) only if he asks what the categories mean.
   - He can answer in any format — "120k 200k 490k current state: 2 deals in redlines notes: Matson MSA due tmrw" is fine.
4. **Parse:** run `parse-call --input "<his full reply>"`. It returns `{commit, best_case, pipeline, current_state, notes}`.
   - First three dollar amounts in text order = Commit, Best Case, Pipeline. Text after `current state:` / `notes:` markers splits into those fields; no markers → remaining text goes to Notes, Current State stays blank.
   - If `ok:false` (fewer than 3 amounts found), show the error and ask him to re-enter just the three numbers — never guess a missing category.
8. **Completeness reminder (rule from {{REVOPS_1}}, 2026-10-02):** before the summary, check all five fields are answered. If any field was skipped or left blank (Current State or Notes), remind him: "Heads up — you left Current State blank. Want to add it? If not, I'll log it as 'Nothing was added.'" Re-ask once. If he confirms leaving it blank, log the literal text `Nothing was added` in that field — never write an empty cell. If Notes was skipped entirely, go back and ask it — Notes is never blank without an explicit answer.
9. **Summary + confirm (HARD GATE — always, rule from {{REVOPS_1}} 2026-10-05):** show all five parsed answers in a summary, ask him to confirm or change any one. Only write after an explicit confirm. Never append off a bare parse without confirmation.
10. **Write:** `append --name "{{SALES_LEADER}}" --commit N --best-case N --pipeline N [--notes T] [--current-state T]`.
11. **Confirm:** "Logged for the forecast week of Oct 6–12. If you resubmit this week, the latest one counts."

## Zero values (rule from {{REVOPS_1}}, 2026-10-05)

`$0` is a real call. If any category is zero, it logs as `$0` in the sheet — never "-", never a blank cell. The Forecast Log number format (columns G–I) is pinned to `$#,##0;-$#,##0;$0` so zeros always render as `$0`. Don't treat a `$0` answer as "no answer" for the completeness reminder — it's complete.

## Number handling

For combined replies use `parse-call --input "<full text>"` (step 4). For a bare dollar answer (when a conversation does go one-at-a-time), parse through `parse --input "<raw>"` — never convert in your head.
- Accepts: `0000000`, `120,000`, `$120K`, `120k`, `1.2M`, `0`, `none` (= 0).
- Rejects negatives (script errors) — tell him no negative numbers.
- No cross-field validation. Commit, Best Case, and Pipeline are independent numbers — the seller and their leader own the relationship between them.

## Writing rules (hard)

- The script appends exactly one row, columns A–K, with RAW serial dates and whole-dollar numbers. Role lands as CRO automatically from the roster. Never edit or delete existing rows — a resubmission is a new row; the sheet's latest-Submitted-At logic picks the winner.
- His calls never roll into the AE roll-up. The sheet handles that; just never write his numbers under any other name.
- Take the confirm moment as the timestamp. If the conversation runs past Monday midnight PT, the confirm time decides the week — tell him the week again in the confirmation.
- If the append returns `ok:false`, tell him it didn't save, and alert {{REVOPS_1}}. Never claim success on a failed write.
- `FORECAST_SHEET_ID` env var points the script at a scratch copy for testing — never test appends against the live tracker.

## Self-serve entry ({{SALES_LEADER}} initiates, any day)

Same as AEs: he can DM the GTM agent any day ("forecast", "change my forecast", "was out Friday") and get the same conversation — the single-question ask, `parse-call`, summary, explicit confirm, then `append`. Append-only + latest-Submitted-At means a resubmit any day Tuesday through Monday becomes that week's call. A Monday submission still counts for the week that just ended.

## Failure modes

- Write fails → tell {{SALES_LEADER}}, alert {{REVOPS_1}}, no success claim.
- {{SALES_LEADER}} asks to see history → run `last --name "{{SALES_LEADER}}"` and share his own latest row only. Never share another person's calls.

## Review requests (rule from {{REVOPS_1}}, 2026-10-02)

When {{SALES_LEADER}} asks to review forecast calls in the weekly sheet, he gets the team roll-up. Run `team [--date YYYY-MM-DD]` in `CRO_forecast_skill.py`: it prints the VP's team-level call plus each AE's latest Forecast Log row for the forecast week (latest submission per person wins), flags anyone who hasn't submitted, and sums the roll-up. The roll-up totals sum AE rows only — the VP team-level call is shown as a separate lens and excluded from the sum to avoid double counting. An AE asking the same question gets only their own row (`last` in `AE_forecast_skill.py`); never show an AE another person's calls.
