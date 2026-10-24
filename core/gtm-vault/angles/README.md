# Angles — Tracked Angle Library

Angles are the messaging hooks used in outbound emails. Each angle has:
- **ID**: Stable identifier for tracking across campaigns
- **Name**: Human-readable label
- **Description**: The core hook/question/insight the angle uses
- **Verticals tested**: Which industries this angle has been sent to
- **Results**: Send count, reply count, positive reply rate
- **Status**: `active` (in use), `testing` (new, being evaluated), `retired` (pulled due to poor performance)
- **Source**: Which sequence step originated this angle

## How It Works

1. New angles start as hypotheses in vertical files under `## Angle Hypotheses`
2. When used in a campaign, they get an entry in `angle-library.json` with status `testing`
3. `feedback_loop.py` updates performance data weekly from Smartlead reply stats
4. Angles with positive rate > median get promoted to the relevant vertical's `## Winning Angles`
5. Angles with positive rate < 50% of median after 100+ sends get flagged in `## Failed Angles`
6. `auto_copy_optimizer.py` uses winning angles when rewriting underperforming copy
7. `vault_campaign_builder.py` reads angles when generating new sequences

## Rules

- Never delete an angle entry. Retire it instead (status: `retired`).
- Angle IDs are kebab-case, descriptive, and stable. Once assigned, never change them.
- Results are cumulative across all campaigns and verticals where the angle was used.
