# Forecast Hygiene Criteria

A deal is "clean" if it passes all checks below. Each failing check adds a flag to the deal.

## Hygiene Flags

| Flag | Condition | Severity |
|------|-----------|----------|
| `NO_CLOSE_DATE` | `closedate` is null or empty | Critical |
| `PAST_CLOSE_DATE` | `closedate` is before today and deal is still open | Critical |
| `STALE_14` | Last engagement (email/call/meeting/note) > 14 days ago | Warning |
| `STALE_21` | Last engagement > 21 days ago | Critical |
| `NO_AMOUNT` | `amount` is null, 0, or missing | Critical |
| `STAGE_STUCK_21` | Stage has not changed in 21+ days | Warning |
| `STAGE_STUCK_30` | Stage has not changed in 30+ days | Critical |
| `NO_CONTACT` | No contact associated with the deal | Critical |
| `NO_COMPANY` | No company associated with the deal | Warning |
| `NO_OWNER` | No HubSpot owner assigned | Critical |
| `GENERIC_NAME` | Deal name matches patterns like "New Deal", "Opportunity", "Test", or is < 10 characters | Warning |
| `NO_NOTES` | Zero deal notes recorded | Warning |

## Severity Definitions

- **Critical**: Report must highlight. Likely affects forecast accuracy or rep accountability.
- **Warning**: Should be fixed, but doesn't immediately break the forecast.

## Hygiene Score Calculation

```
hygiene_score = (deals with 0 flags / total open deals) × 100
```

Displayed as a percentage with color: 90%+ = green, 70-89% = yellow, <70% = red.

## Report Display

In the Hygiene section, group flagged deals by flag type. For each flagged deal show:
- Deal name (linked to HubSpot)
- Rep name
- Amount
- Close date
- Days since last activity
- List of flags (badge style, color-coded by severity)

Sort: Critical flags first, then Warning. Within each severity, sort by amount descending (biggest at-risk deals first).

## Notes for Analysis

When generating "What Must Happen This Week" for a hygienically dirty deal:
- `NO_CLOSE_DATE` or `PAST_CLOSE_DATE` → rep must get a committed close date on the call this week
- `STALE_21` or `STALE_30` → rep must make contact this week or move deal to appropriate stage (or close lost)
- `NO_AMOUNT` → rep must get a budget number this week before deal stays in forecast
- `STAGE_STUCK_30` → escalate: what is blocking stage progression?
