# {{COMPANY}} Outbound & Marketing Skills Catalog

> Master reference for all installed skills relevant to our outbound/marketing pipeline.
> Built 2026-06-30 per Jason Polanco. Update when skills are added or retired.

---

## Pipeline Architecture

```
Signal Discovery → Batch Builder → Clay Dispatch → Clay Enrichment → Smartlead Campaigns
     ↓                  ↓                                                    ↓
  seed list        volume batch                                     5-step sequences
  + discovery      + ICP titles                                     + champion campaigns
  + signals        + firmographics                                  + A/B tests
```

## Skill Categories & When to Use Them

### 1. ANTI-SLOP / VOICE (apply to ALL written content)

| Skill | Location | When to use | Key feature |
|-------|----------|-------------|-------------|
| {{COMPANY}} Voice Prompt | `references/company-voice-system-prompt.md` | ALWAYS — read before drafting anything | {{COMPANY}}-customized Sections 0-4 |
| humanizer (original) | `humanizer/SKILL.md` | Audit pass — 29 patterns | Voice calibration from writing samples |
| avoid-ai-writing | `skills/avoid-ai-writing/SKILL.md` | Deepest pattern library — 49 categories, 109 words | 3-tier severity, detect-only mode |
| humanizer-blader | `skills/humanizer-blader/SKILL.md` | Same as humanizer but updated repo | 33 patterns, Lisbon before/after example |
| humanizer-aboudjem | `skills/humanizer-aboudjem/SKILL.md` | Scoring — 0-100 AI-tell score | Burstiness measurement, humanizer-context.md auto-load |
| no-slop | `skills/no-slop/SKILL.md` | Constraint-first — prevent slop during drafting | 13 rules, conditional bans |
| unslop | `skills/unslop/SKILL.md` | Pre-send quality gate with Python scripts | `banned_phrase_scan.py`, `readability_metrics.py`, rubric scoring (32/40 pass) |
| no-ai-slop-rossmann | `skills/no-ai-slop-rossmann/` | Voice fingerprint methodology | Corpus analysis method, banned-words reference |
| slopless-rules | `skills/slopless-rules/writing-voice.md` | "Hollow enthusiasm" bans | Catches "resonated", "keeps me up at night", "food for thought" |

**Workflow:** {{COMPANY}} Voice Prompt → draft → avoid-ai-writing detect mode → humanizer audit → unslop scoring → fix

### 2. OUTBOUND EMAIL & SEQUENCES

| Skill | Location | When to use |
|-------|----------|-------------|
| cold-email | `skills/cold-email/SKILL.md` | Writing cold outreach sequences |
| cold-email-coreyhaines | `skills/cold-email-coreyhaines/SKILL.md` | B2B cold email + follow-up (Corey Haines framework) |
| email-sequence | `skills/email-sequence/SKILL.md` | Drip campaigns, lifecycle email flows |
| bdr-humanizer | `skills/bdr-humanizer/SKILL.md` | Specifically for BDR outbound copy |
| sales-cadence (sales-skills) | `skills/sales-skills/skills/sales-cadence/SKILL.md` | Multi-channel outbound cadence design with timing + A/B |
| copywriting | `skills/copywriting/SKILL.md` | Landing pages, homepage, any marketing copy |
| copy-editing | `skills/copy-editing/SKILL.md` | Editing existing copy |
| copy-anatomy (realjaymes) | `skills/marketingagentskills/skills/copy-anatomy/SKILL.md` | Reverse-engineer competitor emails into reusable templates |

### 3. CLAY & PIPELINE OPERATIONS

| Skill | Location | When to use |
|-------|----------|-------------|
| clay-gtm-outbound (realjaymes) | `skills/marketingagentskills/skills/clay-gtm-outbound/SKILL.md` | Design/optimize Clay workflows for prospecting + signal detection |
| revops | `skills/revops/SKILL.md` | Revenue operations, pipeline analysis |
| revops-coreyhaines | `skills/revops-coreyhaines/SKILL.md` | RevOps frameworks (Corey Haines version) |
| workflow-automation-agent | `skills/workflow-automation-agent/SKILL.md` | Building automation workflows |

### 4. ICP, TARGETING & RESEARCH

| Skill | Location | When to use |
|-------|----------|-------------|
| icp-learner | `skills/icp-learner/SKILL.md` | Learning/refining ICP from data |
| icp-persona (realjaymes) | `skills/marketingagentskills/skills/icp-persona/SKILL.md` | Generate ICP + buyer persona docs |
| customer-research | `skills/customer-research/SKILL.md` | Customer research synthesis (Corey Haines) |
| customer-research-hyperfx | `skills/customer-research-hyperfx/SKILL.md` | Mine Reddit/YouTube/G2/Twitter for VOC |
| competitor-profiling | `skills/competitor-profiling/SKILL.md` | Research + profile competitors from URLs |
| competitive-intelligence | `skills/competitive-intelligence/SKILL.md` | Competitive intel gathering |
| competitor-intel-hyperfx | `skills/competitor-intel-hyperfx/SKILL.md` | Full competitor battle cards (site + social + search + AI-search) |
| competitor-alternatives | `skills/competitor-alternatives/SKILL.md` | Competitor comparison pages for SEO/sales |

### 5. SALES ENABLEMENT & CALL REVIEW

| Skill | Location | When to use |
|-------|----------|-------------|
| sales-enablement | `skills/sales-enablement/SKILL.md` | Sales enablement materials |
| sales-enablement-coreyhaines | `skills/sales-enablement-coreyhaines/SKILL.md` | Playbooks, launch plans |
| sales-coach | `skills/sales-coach/SKILL.md` | Sales coaching |
| sales-forecast-report | `skills/sales-forecast-report/SKILL.md` | Pipeline forecast reporting |
| sales-call-review (sales-skills) | `skills/sales-skills/skills/sales-call-review/SKILL.md` | Call review with MEDDPICC/SPIN scoring |
| sales-granola (sales-skills) | `skills/sales-skills/skills/sales-granola/SKILL.md` | Granola API integration |

### 6. STRATEGY FRAMEWORKS (book-based, use for specific deliverables)

| Skill | Location | Framework |
|-------|----------|-----------|
| predictable-revenue | `skills/predictable-revenue/SKILL.md` | Aaron Ross — outbound sales machine |
| hundred-million-offers | `skills/hundred-million-offers/SKILL.md` | Alex Hormozi — irresistible offers |
| crossing-the-chasm | `skills/crossing-the-chasm/SKILL.md` | Geoffrey Moore — mainstream adoption |
| obviously-awesome | `skills/obviously-awesome/SKILL.md` | April Dunford — positioning |
| storybrand-messaging | `skills/storybrand-messaging/SKILL.md` | Donald Miller — brand messaging |
| influence-psychology | `skills/influence-psychology/SKILL.md` | Cialdini — persuasion psychology |
| contagious | `skills/contagious/SKILL.md` | Jonah Berger — viral ideas |
| made-to-stick | `skills/made-to-stick/SKILL.md` | Chip & Dan Heath — memorable messaging |
| cro-methodology | `skills/cro-methodology/SKILL.md` | Making Websites Win — CRO |
| lean-analytics | `skills/lean-analytics/SKILL.md` | Alistair Croll — metrics-driven growth |
| marketing-psychology | `skills/marketing-psychology/SKILL.md` | Behavioral science for marketing |

### 7. SEO & CONTENT

| Skill | Location | When to use |
|-------|----------|-------------|
| ai-seo | `skills/ai-seo/SKILL.md` | AI search optimization (get cited by LLMs) |
| seo-audit | `skills/seo-audit/SKILL.md` | Technical + on-page SEO audit |
| seo-research-hyperfx | `skills/seo-research-hyperfx/SKILL.md` | Keyword research, SERP analysis, AI search visibility |
| content-strategy | `skills/content-strategy/SKILL.md` | Content planning |
| social-content | `skills/social-content/SKILL.md` | LinkedIn, Twitter/X, Instagram content |
| site-architecture | `skills/site-architecture/SKILL.md` | Website information architecture |
| schema-markup | `skills/schema-markup/SKILL.md` | Structured data |
| programmatic-seo | `skills/programmatic-seo/SKILL.md` | SEO at scale with templates |

### 8. GROWTH & CRO

| Skill | Location | When to use |
|-------|----------|-------------|
| page-cro | `skills/page-cro/SKILL.md` | Landing page conversion optimization |
| signup-flow-cro | `skills/signup-flow-cro/SKILL.md` | Signup flow optimization |
| onboarding-cro | `skills/onboarding-cro/SKILL.md` | Post-signup onboarding |
| form-cro | `skills/form-cro/SKILL.md` | Form optimization |
| popup-cro | `skills/popup-cro/SKILL.md` | Popup/modal optimization |
| ab-test-setup | `skills/ab-test-setup/SKILL.md` | A/B test design |
| launch-strategy | `skills/launch-strategy/SKILL.md` | Product launch planning |
| pricing-strategy | `skills/pricing-strategy/SKILL.md` | Pricing decisions |
| churn-prevention | `skills/churn-prevention/SKILL.md` | Reduce churn, cancellation flows |
| lead-magnets | `skills/lead-magnets/SKILL.md` | Lead magnet creation |
| referral-program | `skills/referral-program/SKILL.md` | Referral/affiliate programs |
| free-tool-strategy | `skills/free-tool-strategy/SKILL.md` | Free tools for lead gen |
| ad-creative | `skills/ad-creative/SKILL.md` | Ad creative generation |
| paid-ads | `skills/paid-ads/SKILL.md` | Paid advertising campaigns |

### 9. MARKETING AGENT SKILLS (realjaymes — 28 skills)

Full repo at `skills/marketingagentskills/skills/`. Key skills for us:
- `clay-gtm-outbound` — Clay workflow design
- `copy-anatomy` — Reverse-engineer copy into templates
- `icp-persona` — ICP + buyer persona generation
- `lifecycle-marketing-campaigns` — Lifecycle campaign flows
- `performance-marketing` — Paid campaign optimization
- `product-launch-gtm` — End-to-end launch planning
- `product-messaging` — Messaging frameworks
- `product-positioning` — Positioning frameworks
- `n8n-automation` — n8n workflow design
- `openclaw` — OpenClaw configuration skill

### 10. SALES SKILLS (sales-skills — 630+ skills)

Full repo at `skills/sales-skills/skills/`. Covers every sales tool imaginable. Key for us:
- `sales-cadence` — Multi-channel outbound design
- `sales-call-review` — MEDDPICC/SPIN scoring
- `sales-granola` — Granola API (we use this)
- `sales-hubspot` — HubSpot platform
- `sales-smartlead` — Smartlead platform
- `sales-clay` — Clay platform
- `sales-apollo` — Apollo platform
- `sales-gong` — Gong platform
- `sales-fathom` — Fathom platform
- `sales-field-sales` — Field sales workflows
- `sales-note-taker` — Note-taker selection guide

---

## Quality Gate: Pre-Send Email Audit

Before any email sequence goes to Smartlead, run this stack:

1. **{{COMPANY}} Voice Prompt check** — does it match our register?
2. **Banned word scan** — `python3 skills/unslop/scripts/banned_phrase_scan.py < email.txt`
3. **Readability metrics** — `python3 skills/unslop/scripts/readability_metrics.py < email.txt`
4. **CTA check** — no banned CTAs per AGENTS.md
5. **Merge tag check** — only `{{variable_name}}`, no Jinja2/Liquid
6. **Send test to Jason** — mandatory before activation

---

## Total Skill Count

- Anti-slop/voice: 9 skills
- Outbound email: 8 skills
- Clay/pipeline ops: 4 skills
- ICP/targeting/research: 7 skills
- Sales enablement: 6 skills
- Strategy frameworks: 11 skills
- SEO/content: 8 skills
- Growth/CRO: 14 skills
- Marketing agent (realjaymes): 28 sub-skills
- Sales (sales-skills): 630+ sub-skills
- **Total: 725+ skills available**

---

_Last updated: 2026-06-30. Update when skills are added, retired, or workflows change._
