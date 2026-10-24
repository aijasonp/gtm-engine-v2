# Deal Confidence Scoring Rubric

Score range: 0–100. Color bands: 0-39 = red, 40-69 = yellow, 70-100 = green.

Start at 60 for any open deal with a valid stage and amount > $0.

## Positive Adjustments (add to score)

| Condition | Points |
|-----------|--------|
| Stage: Closed Won (should not appear in open deals, but +15 if mistakenly included) | +15 |
| Stage: Contract Sent / Negotiation | +15 |
| Stage: Decision Maker Bought In / Verbal Commit | +12 |
| Stage: Evaluation / POC in Progress | +8 |
| Recent engagement: meeting or call within last 7 days | +10 |
| Recent engagement: email reply (not auto) within last 5 days | +7 |
| Close date is 14+ days in the future (reasonable timeline) | +5 |
| Deal has a note with clear next steps written | +5 |
| Deal amount matches or exceeds $50K | +3 |
| Multiple contacts associated (champion + exec sponsor) | +5 |
| Deal has been in current stage < 14 days (progressing) | +5 |
| Company record linked | +3 |

## Negative Adjustments (subtract from score)

| Condition | Points |
|-----------|--------|
| No close date set | -20 |
| Close date is in the past (deal still open) | -25 |
| No activity in last 14 days | -15 |
| No activity in last 21 days | -25 |
| No activity in last 30+ days | -35 |
| Amount = $0 or null | -20 |
| Stage has not changed in 21+ days | -10 |
| Stage has not changed in 30+ days | -20 |
| No contact associated | -15 |
| Only one contact (no exec sponsor) | -5 |
| Deal name is generic (e.g., "New Deal", "Opportunity") | -5 |
| No company associated | -10 |

## Score Interpretation

| Range | Color | Label | Meaning |
|-------|-------|-------|---------|
| 80-100 | Green | High | Deal on track. Clear next steps, active engagement, reasonable timeline. |
| 65-79 | Green | Promising | Good signals but minor gaps (e.g., no exec sponsor, light activity). |
| 50-64 | Yellow | Monitor | Some risk. Needs attention this week. |
| 35-49 | Yellow | At Risk | Multiple warning signs. Likely needs intervention. |
| 0-34 | Red | Critical | Severely stalled or missing key information. Escalate or close. |

## Notes

- Cap score at 100, floor at 0.
- For deals in "Closed Lost" or "Closed Won" stages, do not score; exclude from report.
- When HubSpot engagement data is sparse (no emails, calls, or meetings logged), treat as 0 recent activity even if last_modified is recent (reps sometimes update fields without logging activity).
- Weight close date proximity when generating "What Must Happen This Week": any deal closing within 7 days with score < 70 is an automatic priority-1 item regardless of score.
