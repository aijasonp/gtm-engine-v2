---
name: competitive-intelligence
description: Produces structured competitive analysis for the product you sell, with SWOT-style comparisons, battlecard sections, objection handling, and deal-specific win/loss framing. Built for BDR objection prep and AE battlecard generation.
---

# Competitive Intelligence Skill

## Overview

When a prospect says "we're already looking at [Vendor X]" or "how are you different from [Y]," reps need a fast, confident, specific answer — not a corporate positioning statement.

This skill produces structured competitive intelligence: head-to-head comparisons, our differentiated angles, objection handling scripts, and deal-specific framing based on what you know about the prospect.

---

## Instructions

### Inputs
Provide one or more of:
- Competitor name(s) to analyze
- Prospect context (industry, size, known pain, current stack)
- Deal stage (cold / discovery / evaluation / final)
- Specific objection or question that triggered this request

### Output options

**Mode A — Head-to-Head Comparison**
> "Compare us vs. [Competitor]"

Produces a structured table + narrative:

| Dimension | Us | [Competitor] |
|-----------|-------|--------------|
| Deployment model | [from product profile] | [e.g., cloud-only] |
| Integrations | [from product profile] | [e.g., single-vendor] |
| Core capability | [lead differentiator] | [their equivalent] |
| Time to deploy | [from product profile] | [e.g., weeks or months] |
| Target buyer | [our buyer] | [e.g., IT admin / procurement] |
| Key weakness | [Honest assessment] | [Honest assessment] |

Followed by:
- **Our strongest angle vs. this competitor** (1-2 sentences, deal-specific)
- **What the competitor will say about us** (so the rep isn't blindsided)
- **How to reframe it**

---

**Mode B — Objection Handler**
> "Prospect said: [exact quote or paraphrase]"

Produces:
- **What they really mean** (the underlying concern behind the objection)
- **Acknowledge** (1 sentence — validate without conceding)
- **Reframe** (pivot to our strength without being defensive)
- **Proof point** (specific example, stat, or customer signal if available)
- **Question to ask back** (keep the conversation moving)

---

**Mode C — Deal-Specific Battlecard**
> "Build a battlecard for this deal: [context]"

Produces a 1-page-equivalent brief:
- Prospect's likely criteria / what they're optimizing for
- Competitors they're probably evaluating
- Our top 3 differentiators most relevant to this deal
- Their most likely objections + responses
- Suggested next step / closing question

---

## Differentiators and Competitors (always anchor here)

Read both from the product profile (`GTM_PRODUCT_PROFILE`):

- `differentiators`: the outcomes we lead with. Pick the 1-3 that matter for this deal.
- `competitors`: each competitor's primary angle and our sourced counter.

If a competitor is not in the profile, research its public positioning, label every point "Based on public positioning, rep should verify," and suggest an addition to the profile.

---

## Constraints

- Never fabricate competitor weaknesses. If you don't have a sourced data point, say "Based on public positioning" or "Rep should verify."
- Objection responses must acknowledge before reframing — never argue directly with the prospect's stated concern.
- Battlecards are deal-specific — don't produce a generic one-size-fits-all card when deal context is available.
- Propose updates to the `competitors` list in the product profile when new intel is confirmed. Flag outdated entries.
- Differentiators are stated as customer outcomes, not product features.
