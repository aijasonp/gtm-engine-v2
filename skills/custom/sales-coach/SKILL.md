---
name: sales-coach
description: Run a roleplay sales call where the user plays the prospect and the AI plays the AE, then get a scored coaching report on discovery, objections and closing. Use when an AE wants to practice a call, rehearse objections, or get coaching feedback before a real meeting.
---

# Sales Coach

## Overview
Simulates an enterprise buying conversation. The user plays the prospect; the AI plays the AE (name from `AE_NAME`, default "Sam"). The script tracks call stages, adapts to the chosen buyer persona, and ends with a coaching report. Seller context (product, ICP, pain points, differentiators, competitors, proof points) comes from the product profile at `GTM_PRODUCT_PROFILE`.

## Step 1: Confirm access
1. `ANTHROPIC_API_KEY` is exported or stored in the env file (`GTM_ENV_FILE`, default `~/.gtm/.env`).
2. `GTM_PRODUCT_PROFILE` points at the deployment's product profile. Without it the AE keeps claims general.

## Step 2: Launch the roleplay
```bash
python skills/sales-coach/sales_coach.py --persona economic_buyer
```
Personas: `economic_buyer` (default), `technical_buyer`, `champion`, `procurement`.

## Step 3: Run the conversation
1. The CLI shows the current stage before every AE turn (Introduction through End conversation).
2. Type prospect replies at the prompt. Enter `EXIT` or `END` to finish and get feedback.
3. Each AE turn is classified into a stage by a small model; dialogue and coaching use a larger model.

## Step 4: Review the coaching report
- Stage progression
- Discovery quality
- Objection handling
- Value alignment
- Close quality
- Score (0-100)
- Top 3 strengths and top 3 improvements
- Suggested alternative phrasing

Use the transcript and report to brief the AE or save to call notes.

## Error handling
- **Missing key:** the script exits with `ANTHROPIC_API_KEY is required`.
- **Network or API errors:** the CLI shows the API error. Retry after checking connectivity; backoff is built in.
- **Persona typo:** the parser lists valid personas and exits.
