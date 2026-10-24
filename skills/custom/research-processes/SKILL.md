---
name: research-processes
description: >
  18 validated web research processes for company intelligence — each a step-by-step prompt
  usable by a GTM agent (web search), Claygent (Clay), or any AI agent.
  Processes: find-profiles, find-competitors, find-reviews, find-news, find-pr-releases,
  find-hiring, find-job-role-insights, find-growth-signals, find-negativity, find-funding,
  find-founders, find-c-suite, find-vp-leadership, find-directors, find-department-heads,
  find-specialist-roles, find-people-creative, find-portfolio-companies.
  All tested at 90%+ accuracy across 25 companies (4 tiers).
  Use when researching any prospect, account, or competitor — before meetings, during POCs,
  or to reignite stalled deals.
---

# Research Processes — Skill Hub

18 battle-tested research processes built with the self-annealing methodology from
`research-process-builder`. Each process is a standalone Claygent/agent prompt.

## How to Use

**As a GTM agent (web search tool):**
Load the relevant `.md` file and follow steps in sequence using web_search for each query.

**As Claygent (Clay enrichment column):**
Paste the process file as the Claygent system prompt. Fill in `{{inputs}}` from your Clay table columns. Each step maps to one enrichment column.

**As any AI agent:**
Paste the process `.md` as the system/instructions. Fill in variables. Agent follows steps, stops when conditions are met, outputs in the specified template.

## Process Index

| Process | File | What It Finds | Accuracy |
|---------|------|---------------|----------|
| Company profile | `find-profiles.md` | Employees, funding, tier, category | Q4.0 |
| Competitors | `find-competitors.md` | Direct competitors + positioning | Q4.0 all tiers |
| Reviews | `find-reviews.md` | Customer + employee reviews (+/-) | Q4.0 all tiers |
| Recent news | `find-news.md` | Partnerships, funding, launches, leadership | Q3.6–4.0 |
| PR releases | `find-pr-releases.md` | Official announcements + blog cadence | Q3.9 |
| Hiring | `find-hiring.md` | Open roles, ATS platform, velocity | Q4.0 |
| Job role insights | `find-job-role-insights.md` | Tech stack, pain points from JDs | Q4.0 |
| Growth signals | `find-growth-signals.md` | Blog, social, community, pricing | Q4.0 |
| Negativity | `find-negativity.md` | Complaints, churn signals, controversy | Q3.4–4.0 |
| Funding | `find-funding.md` | Round type, amount, date, investors | 87.5–100% |
| Founders / CEO | `find-founders.md` | Founders, CEO, president | Q4.0 |
| C-suite | `find-c-suite.md` | CTO/CPO/CISO + CMO/CRO/CFO | Q3.7–3.8 |
| VP leadership | `find-vp-leadership.md` | VP Sales, Marketing, Engineering | Q3.8–3.9 |
| Directors | `find-directors.md` | Director-level across functions | Q4.0 |
| Department heads | `find-department-heads.md` | Head of Growth/CS/Partnerships + RevOps | Q3.6–3.9 |
| Specialist roles | `find-specialist-roles.md` | HR/People, Finance/Legal, Staff Engineers | Q3.3–4.0 |
| People (creative) | `find-people-creative.md` | People via media, data platforms, content | Q3.5–3.9 |
| Portfolio companies | `find-portfolio-companies.md` | PE firm portfolio count + firm type | High |

## Key Rules (from methodology)

- Always use `{{category}}` for names ≤6 chars or common words (Clay, Keep, Cursor)
- OR operators are the highest-leverage technique — combine synonyms into one query
- Never hardcode the year — use `{{current_year}}` (Clay: `YEAR({Created At})`)
- `site:reddit.com` is broken — use `[name] reddit discussion` instead
- `site:rocketreach.co` NOT `.com` — `.com` returns zero results
- Kill lists save 30–40% of your search budget — respect them

## Suggested Workflows

**Pre-meeting brief:** `find-profiles` → `find-c-suite` → `find-growth-signals`
**Deal reignite:** `find-news` + `find-funding` → find the trigger event
**POC prep:** `find-hiring` → `find-job-role-insights` on their open security roles
**Competitive intel:** `find-competitors` + `find-reviews` on what they're evaluating
**Loss audit:** `find-negativity` + `find-news` on any deal that went dark

## Source

Cloned from https://github.com/MitchellkellerLG/research-process-builder
