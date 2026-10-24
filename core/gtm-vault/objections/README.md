# Objections — Pattern Library

Objection patterns are captured from two sources:
1. **Reply analysis**: `reply_monitor.py` extracts objection patterns from OBJECTION-classified replies
2. **Call transcripts**: Post-call brief pipeline extracts objections from discovery and demo calls

Each pattern includes:
- **Pattern ID**: Stable identifier
- **Objection text pattern**: The core objection, generalized from specific instances
- **Frequency**: How many times this objection has been observed
- **Verticals**: Which industries this objection appears in
- **Recommended handle**: Suggested response approach
- **Source**: "reply" or "call"
- **Examples**: Verbatim examples from actual replies/calls (anonymized)

## How It Works

- `reply_monitor.py` uses {{COMPANY}} API to extract objection patterns from reply text
- Patterns are matched against existing entries by semantic similarity
- New patterns get a new entry. Known patterns get frequency incremented.
- `vault_campaign_builder.py` reads objection patterns to pre-handle them in generated copy
- Vertical files get updated with relevant objection patterns in `## Objection Patterns` section
