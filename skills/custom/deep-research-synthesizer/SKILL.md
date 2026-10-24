---
name: deep-research-synthesizer
description: Transforms raw research inputs (company info, news, job postings, tech signals) into a structured, actionable account brief. Built for BDR pre-call and pre-email prep — filters low-value data, surfaces patterns, produces a ready-to-use intelligence summary.
---

# Deep Research Synthesizer

## Overview

Pre-call research is the difference between a cold call and a warm conversation. This skill takes messy inputs — search results, LinkedIn snippets, news articles, job postings, tech stack data — and produces a clean, structured account brief with clear implications for outreach.

Output is always actionable, never encyclopedic. The goal is not comprehensiveness — it's giving the rep exactly what they need to open a conversation with relevance.

---

## Instructions

### Inputs accepted
Provide any combination of:
- Company name + URL
- Raw search results or article text
- LinkedIn profile snippets (executive or company page)
- Job posting text
- Tech stack data (from BuiltWith, G2, etc.)
- HubSpot notes or activity history
- Trigger event (funding, hire, expansion, news item)

### Output format: Account Brief

Produce the brief in this exact structure:

---

**ACCOUNT BRIEF: [Company Name]**  
*Prepared for: [Rep name or "BDR review"]*  
*Date: [today]*

**Company snapshot**
- Industry, size, HQ, business model (2-3 sentences max)
- Key business context (growth stage, regulatory environment, recent change)

**Who matters**
- Decision maker name, title, tenure, LinkedIn signal
- Champion / economic buyer distinction if known
- Any known org changes (new hire, restructure, departure)

**Why now (trigger)**
- The specific signal that makes this account warm today
- Recency and relevance scored: 🔴 Hot (< 30 days) | 🟡 Warm (30-90 days) | ⚪ Cold (90+ days)

**Their AI / security posture**
- Known tools in use (from job postings, tech stack, press)
- Gaps or signals of pain (e.g., hiring for roles that own the problem, executive statements, compliance language)
- Competitor presence if known

**Outreach angle**
- One-line thesis: why our product is relevant to *this* account *right now*
- Suggested opening hook (can be fed directly into SCQA framework)
- Objections to anticipate

**Research confidence**
- High / Medium / Low based on data quality
- What's missing that would improve confidence

---

### Processing rules

1. **Filter ruthlessly.** If a data point doesn't change what you'd say or how you'd say it, cut it.
2. **Prioritize recency.** A 2-year-old funding round is background. A hire last month is a trigger.
3. **Infer from job postings.** A company hiring a new lead for the function we sell into is signaling pain before they've admitted it publicly.
4. **Read between the lines.** An executive speaking at a compliance conference → regulatory pressure → the part of our story that answers that pressure is relevant.
5. **Always produce an outreach angle.** Even low-confidence briefs should end with a hypothesis the rep can test.

---

## Constraints

- Never include information that can't be sourced from the inputs provided. Don't fabricate details.
- Keep the full brief under 400 words. If you're going longer, you're being encyclopedic, not useful.
- The outreach angle must reference the specific trigger — not a generic "this category is important" statement.
- If inputs are thin, say so explicitly in the Research Confidence section and suggest what to look up.
- Do not speculate about revenue, headcount, or financial details unless sourced from a credible signal.
