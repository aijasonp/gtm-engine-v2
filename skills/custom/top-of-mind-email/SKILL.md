---
name: top-of-mind-email
description: Draft a short, low-pressure email to a prospect between calls that shares one or two relevant third-party articles or data points, without naming our product. Use when a deal is waiting on the next meeting and the AE wants to stay top of mind.
---

# Top-of-Mind Email (Stay Top of Mind Between Calls)

## Purpose
Draft a short, low-pressure email to a prospect between calls. The email shares one or two relevant, recent, **non-competitive** 3rd-party articles or data points that reinforce the value of our product **without explicitly naming our product**. The goal is NOT to get a response. It is to keep us top of mind while waiting for the next meeting.

## Inputs Required (request these BEFORE drafting)
Ask the requester to attach/provide ALL of the following. Do not draft until the transcript is provided:

1. **Call transcript** (required). Attach the transcript file (docx, txt, or paste). This is the primary source of context.
2. **Follow-up email sent after the first call** (strongly recommended). Paste or attach it so the new email matches tone, naming, and the specific use cases already discussed.
3. **Next meeting date** (recommended). Used for the "while we wait for the 14th" framing. If not given, use a generic "while we wait for our next call."
4. **Any other relevant context** (optional): prospect's stack, industry, specific concerns, who is on the call, the account manager's name.

If any of 1-3 is missing, ask for it before creating the email. Do not proceed on the transcript alone if the follow-up email exists and is available.

### Delivery details (ask AFTER drafting, before sending)
After the email is drafted, ask the requester for:
1. **Do they want a draft email written?** Confirm they want the draft (with a relevant subject line).
2. **Subject line:** must start with the seller's company name and a colon, as set in the product profile `product_name` (e.g., `<Company>: A quick share while we wait`).
3. **Recipient email address(es):** who to send it to.
4. **Send date and time in the recipient's local time zone.** Ask for the time in their local time zone, plus the date.
   - If they give a time: schedule/send for that date and time.
   - If they do NOT give a time: tell them the email is in their draft folder to send when ready (do not send automatically).
   - If they say "now": send it right away.

## Steps

### 1. Read the transcript for context
Extract from the call:
- The prospect's stated priorities and pain points (e.g., defensive vs offensive, threat hunting, detection triage, insider threat, governance/control of agents, local models, data staying in-environment).
- Their existing stack (e.g., "we are a CrowdStrike shop") — this matters for the competitive check.
- Their tone and the relationship (informal, technical, etc.).
- The specific next meeting date and who will attend.

### 2. Find a relevant, recent, NON-COMPETITIVE 3rd-party source
- **Recency:** the article or data point must be from the **last 2-3 weeks**.
- **Relevance:** it should validate the prospect's stated concern or the value we provide, without naming our product.
- **Non-competitive (critical):** do NOT use a vendor's own thought-leadership or marketing if that vendor competes with us or is already in the prospect's stack. A vendor blog that positions itself as the leader in the exact space you are pitching reinforces the competitor, not us. Prefer:
  - Neutral trade/industry news (e.g., BleepingComputer, The Hacker News, SecurityWeek, Help Net Security).
  - Independent research, analyst reports, or surveys.
  - A vendor's *research/landscape* piece is acceptable only if it is framed as neutral research, not product marketing, and the vendor is not a direct competitor in the prospect's stack.
- **Verify before sending:** fetch the article URL and confirm (a) it exists, (b) the publish date is within the last 2-3 weeks, (c) the headline/claim matches what you will reference. Never fabricate data, stats, or article content.

### 3. Write the email
- **Tone:** professional but informal, human, low-pressure. No em dashes. No AI slop (no "leverage," "utilize," "game-changing," "it's worth noting," "in today's landscape," hollow enthusiasm). Varied sentence length. Direct and specific.
- **Structure (keep it short):**
  1. Greeting (first name).
  2. One line: since we are waiting on [date], wanted to pass along something relevant to what we talked about.
  3. One or two sentences on what the article/data point is and why it connects to something they raised on the call (reference their words, e.g., "the reality you flagged on the call").
  4. The link(s). Keep it simple — one or two links max.
  5. Low-pressure close: "No need to reply. Just figured it was worth sharing while we wait. Looking forward to the 14th." (adjust date).
  6. Sign-off.
- **Do NOT** ask for a response, book time, or push next steps. The sole goal is top of mind.

### 4. Humanize and self-check
- Read it aloud. Cut anything that sounds templated or salesy.
- Confirm: no em dashes, no AI-slop phrases, no fabricated data, links verified, non-competitive source, within 2-3 weeks.

## Output
Return the final email ready to send, plus (briefly) the source(s) used and why they are relevant and non-competitive, so the requester can trust the choice. Then confirm the delivery plan per the Delivery details above (draft vs scheduled vs send now, subject, recipient, date/time).

## Example (real, Sep 2026)
Prospect: Inova, a CrowdStrike shop, interested in defensive agents (threat hunting, detection triage, insider threat) and controlling AI agents in their network ("versus letting it be the wild west"). Next meeting Sep 14.
- Rejected: CrowdStrike's "Teaching AI to Reason Through Detection Triage" — vendor marketing, reinforces a competitor already in the stack.
- Used: BleepingComputer, "Nearly 700 rogue AI agents coordinated in the Hugging Face attack" (Sep 1, 2026) — neutral trade news validating the exact governance/control concern from the call.
