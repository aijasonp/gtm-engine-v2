# Customer Language — Phrase Library

Actual words and phrases prospects use when talking about their AI governance challenges. Captured from:
1. **Reply text**: `reply_monitor.py` extracts meaningful phrases from prospect replies
2. **Call transcripts**: Post-call brief pipeline extracts language from discovery and demo calls

Each entry includes:
- **Phrase**: The actual words the prospect used
- **Context**: What they were talking about when they said it
- **Source**: "reply" or "call"
- **Vertical**: Which industry the prospect is in
- **Sentiment**: positive, negative, neutral
- **Date captured**: When this was recorded

## Why This Matters

Cold emails that use the prospect's own language get replies. Emails that use marketing jargon get deleted. This library is how we learn to speak our prospects' language instead of our own.

`vault_campaign_builder.py` reads this library when generating copy and incorporates captured phrases into email language.
