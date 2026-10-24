# Signal-Sayability Matrix: {{COMPANY}} Outbound Playbook

**PERMANENT: Jason mandate 2026-09-29**

Purpose: classify every signal type by whether it can be referenced in outreach copy (sayable) or whether it only tells us when to send (timing trigger, never mention).

---

## Core Rule

Every signal gets a sayability class BEFORE it can be used in copy. Copy subagents, copy_review gates, and dispatch reviewers must check referenced signals against this matrix. A signal with no class entry here is treated as RED until this file is updated. Violation of a RED class, or a YELLOW class referenced without the safe phrasing pattern, equals copy rejection. No exceptions, no "it felt natural."

---

## The Three Classes

### GREEN: safe to reference

Public, prospect-visible, non-creepy. The prospect announced it, filed it, or posted it themselves. Referencing it builds credibility: it shows we did homework on their terms, not surveillance on ours.

### YELLOW: reference with care

Public but sensitive. The fact is available, but citing it verbatim reads like monitoring. Reference only obliquely, at the level of a general trend. Never cite counts, dates, URLs, or exact phrasing from the source.

### RED: never mention

Signals that reveal surveillance, internal data, tracking pixels, or would embarrass or alarm the prospect. These are timing triggers ONLY. They decide when we send and who we prioritize. They never appear in copy, subject lines, call openers, or LinkedIn messages. Not obliquely. Not "a little bird told me." Never.

---

## The Matrix

Signal types below are enumerated from the live pipeline: `signal_scanner.py` (4 tiers), `outbound-config.yaml` signal types, `clay-webhooks.yaml` workbook schemas (WB1/WB3/WB4), `smartlead_hot_handoff.py` engagement signals, `linkedin_radar.py`, `company_discovery.py` breach sourcing, and `lead_context.py` enrichment fields.

| # | Signal type | Source in pipeline | Class | How to reference (GREEN/YELLOW) or why never (RED) | Safe phrasing pattern |
|---|---|---|---|---|---|
| 1 | SEC 10-K / 10-Q filing, Risk Factors or MD&A discussing AI or security risk | `signal_scanner.py` Tier 1, `signal_source="10-K"` | GREEN | They filed it with the SEC. It is the most public document a company produces. Quoting it positions us as reading what their own lawyers wrote. | "Your latest 10-K calls out AI governance risk directly." / "We work with teams whose filings flag the same AI risk language yours does." |
| 2 | Major AI initiative / AI investment announcement (press release, earnings call, tier-1 press) | `signal_scanner.py` Tier 2, `signal_source="ai_initiative"`, WB1 `FUNDING_EXPANSION` when investment-sized | GREEN | They announced it publicly, often with a dollar figure. They want people to know. | "Saw the announcement on your GenAI rollout." / "Teams scaling AI programs like the one you announced usually hit governance gaps around month three." |
| 3 | Funding round (Series raise, stated AI budget, capex commitment) | `outbound-config.yaml` `funding`, WB1 `FUNDING_EXPANSION` | GREEN | They announced it. Investors announced it. TechCrunch covered it. Safe to name the round and amount if public. | "Congrats on the Series C." / "Post-raise is usually when AI governance tooling gets budget." |
| 4 | New AI / security executive appointment (CISO, Chief AI Officer, Chief Data Officer, Head of AI) | `signal_scanner.py` Tier 4, `signal_source="exec_change"`, `outbound-config.yaml` `leadership_change`, WB1 `SECURITY_LEADER_NEW` | GREEN | The company issued a press release. The exec updated their own LinkedIn. Naming the person and role is fine. | "Saw [Name] joined as CISO. New security leadership usually means a 90-day tooling review." |
| 5 | AI / security leadership hiring (job posts for Head of AI, AI Governance, ML Security, CISO) | `signal_scanner.py` Tier 3, `signal_source="hiring"`, `outbound-config.yaml` `hiring`, WB1 `SCALE_BOTTLENECK` / `SECURITY_LEADER_NEW` | YELLOW | Job posts are public, but citing specific counts, exact titles, or "we saw your 47 openings" reads like scraping. Generalize to the team level. Never quote the posting text. | "Teams growing their AI security function right now..." / "When companies staff up on ML security, governance usually lags the hires." NEVER: "Your 12 open security roles" or "saw your Head of AI posting on LinkedIn." |
| 6 | Tech adoption / AI governance language in public materials (LLM deployment, model governance, AI policy) | `outbound-config.yaml` `tech_adoption`, WB1 `GOVERNANCE_GAP` | GREEN | Public statements, docs, blog posts, conference talks. They said it on the record. | "Your team's public work on model governance is exactly what we help operationalize." |
| 7 | Competitor connection / competitor tool evaluation (evidence they use or evaluate Claude, OpenAI, Copilot) | `outbound-config.yaml` `competitor_evaluation`, WB3 `competitor_tool` evidence, `COMPETITOR_DISPLACEMENT` | RED | NEVER mention. This is the single most sensitive signal we hold. Saying "we saw you're evaluating OpenAI" tells the prospect we are watching their vendor stack. It burns the deal and torches our reputation. Timing trigger only: it tells us displacement messaging fits and when to send. | Never referenced. Internally: route to WB3 competitor displacement campaign. In copy: talk about OUR capability, never their vendor. |
| 8 | Breach history / data breach disclosure / ransomware incident | `company_discovery.py` breach queries, `typesafe_client.py` `breach_recovery` | RED | NEVER mention. Referencing a prospect's breach is the fastest way to end a conversation. It embarrasses the security team, implies we are tracking their failures, and often touches active legal or regulatory exposure. Timing trigger only: post-breach accounts get prioritized because budgets open. | Never referenced. Internally: bump priority, route to security-outcome messaging. In copy: talk about industry risk, never their incident. |
| 9 | Smartlead / Lemlist engagement data (email opens, clicks, hot opens, open_count) | `smartlead_hot_handoff.py`, `lemlist_reply_monitor.py`, unified webhook events | RED | NEVER mention. "I saw you opened my email three times" is surveillance. It comes from our tracking pixel, which the prospect never consented to. Timing trigger only: hot opens create Aircall tasks and send-time priority. | Never referenced. Internally: `open_count >= 2` triggers phone task. In copy: nothing. The prospect should never know we saw the open. |
| 10 | HubSpot activity (page views, form fills, lifecycle stage, prior campaign enrollment) | HubSpot CRM, `lead_context.py` `prior_campaign` | RED | NEVER mention. Website tracking and CRM activity are our internal data. "I noticed you visited our pricing page" is the canonical creepy SDR line. Timing trigger only: it informs send time and which sequence. | Never referenced. Internally: route by lifecycle stage. In copy: nothing about their visits or form fills. |
| 11 | LinkedIn radar data (connections, invitations, message-less invites) | `linkedin_radar.py`, `linkedin_file_ingest.py` | RED | NEVER mention the tracking itself. "I saw you viewed my profile" or referencing connection-graph data reads as LinkedIn stalking. Exception: if the prospect sent US a message or posted publicly, that message or post is GREEN (see #14). | Never referenced as radar output. Internally: route warm connections to AEs. In copy: only reference content the prospect themselves published. |
| 12 | Tech stack signals (enrichment fields: SIEM, cloud provider, security tooling) | `lead_context.py` `tech_stack_signals`, Clay enrichment | YELLOW | Tech stack data comes from enrichment vendors, not from the prospect. Saying "we know you run Splunk" reveals third-party profiling. Oblique reference only, and only when the stack is genuinely public (job posts, conference talks, engineering blog). | "Teams running cloud-native SIEM at scale..." / "Security teams on AWS usually hit this governance gap." NEVER: "Our data shows you use CrowdStrike." |
| 13 | Clay enrichment fields (employee count, revenue, industry, HQ location) | Clay Table B, `lead_context.py` | YELLOW | Firmographics are static enrichment, not signals. Referencing exact revenue or headcount reads like a data broker dump. Round and generalize. | "Mid-size banks" / "enterprise insurance teams." NEVER: "Your 4,732 employees" or "your $1.2B revenue." |
| 14 | Prospect's own public posts (LinkedIn post, conference talk, blog post by the prospect on the exact topic) | Manual research, pre-call briefs | GREEN | They published it under their own name. Quoting a prospect's own public words back to them is the strongest credibility move in outbound. | "Your post on AI governance last week nailed the exact problem we solve." |
| 15 | Personal social media activity (personal tweets, personal LinkedIn activity unrelated to the prospect's professional posts) | Any scraping of personal accounts | RED | NEVER mention. Personal social activity is off-limits unless the prospect posted publicly about the exact topic we are reaching out on (then it falls under #14). Anything else is surveillance of a person, not research on an account. | Never referenced. If it is not a public professional post on the outreach topic, it does not exist for copy purposes. |
| 16 | Jev / TypeSafe scores (ICP score, signal quality score, reply classification) | `typesafe_client.py`, `jev_signal_scorer.py` | RED | NEVER mention. These are our internal scoring outputs. "Our AI scored you as a priority account" is insulting and reveals our automation. Timing and routing only. | Never referenced. Internally: gates dispatch priority. In copy: nothing. |
| 17 | Suppression / exclusion list membership | `clay-webhooks.yaml` suppression, `outbound-config.yaml` | RED | NEVER mention. If a domain is suppressed, there is no copy. If a prospect asks why they were or were not contacted, the answer is routing logic, not a list. | Never referenced. |
| 18 | Aircall call outcomes (prior dials, voicemails, call recordings) | `aircall_insight_cards.py`, unified webhook `call.*` events | YELLOW | Prior calls to the SAME prospect can be referenced ("when we spoke in March"). Call metadata (we called you 6 times, you did not pick up) is surveillance framing. | "When we spoke earlier this quarter..." NEVER: "I've called six times" or "saw you missed my call Tuesday." |
| 19 | Event attendance / sponsorship (WB2 was killed 2026-06-24, retained for reference) | `clay-webhooks.yaml` wb2_event (killed) | GREEN when public | If the company publicly sponsored or spoke at an event, referencing it is fine. If we scraped an attendee list, it is RED. | "Saw your team at Black Hat." (public sponsorship) NEVER: "Our list shows three of your engineers attended." |
| 20 | Context.dev news items (AI-relevant company news fallback) | `signal_scanner.py` `_contextdev_news_signal`, `context_tags=["ai_investment","contextdev"]` | GREEN | Public news articles. Same rules as Tier 2 press: they published it, we can reference it. | "Saw the coverage of your AI platform launch." |

---

## Special Cases (Jason-called, non-negotiable)

**Competitor connections = NEVER mention.** Row 7 above. RED, timing only. This includes any phrasing that implies we know their vendor stack, their evaluation shortlist, or their renewal dates. The prospect should believe we reached out because of THEIR public moves, not because we know who they buy from.

**Funding = GREEN.** Row 3. They announced it. Safe to congratulate, safe to name the round, safe to tie to budget timing.

**Job postings = generalize, always.** Row 5. Never cite specific counts, specific role titles verbatim, or the posting URL. "Growing the security team" is the ceiling. "Saw your Staff ML Security Engineer post on Indeed from 11 days ago" is a rejection.

**Engagement data (opens, clicks) = RED in copy, gold in timing.** Row 9. It decides when we call and what we send next. It never appears in the message itself.

**Personal social media = RED unless the prospect posted publicly about the exact topic.** Rows 14 and 15. A public LinkedIn post about AI governance by the prospect is GREEN. Their weekend tweet is RED. Their spouse's Instagram is not a signal, it is a restraining order.

---

## Enforcement

This matrix is a gate, not a guideline.

1. **Copy review gates must check it.** `copy_reviewer.py`, `copy_critique_loop.py`, and `dispatch_reviewer.py` (all at `~/projects/scripts/outbound-engine/`) must validate that every signal referenced in draft copy maps to a GREEN row, or a YELLOW row using the safe phrasing pattern. Any RED reference, any YELLOW reference with verbatim counts or URLs, and any signal not listed in this matrix must fail review.

2. **File path convention.** This matrix lives at `~/.openclaw/workspace/references/signal-sayability-matrix.md`. Copy subagents and review scripts reference it by that path. When a new signal type is added to the scanner or a workbook schema, the same PR must add a row here. A signal with no row is RED by default.

3. **Rejection language.** When a reviewer rejects copy on matrix grounds, the rejection must cite the row number and class: "Rejected: references signal #9 (engagement data), class RED, timing trigger only."

---

## Why This Matters

- **Creepy surveillance kills deals.** One "we saw you opened our email" or "we know you're evaluating OpenAI" and the prospect forwards us to their CISO as a cautionary tale. We sell security. We cannot sound like the threat.

- **Referencing public signals builds credibility.** Quoting a 10-K, congratulating a funding round, or referencing a prospect's own published post proves we did real homework. That is the difference between "personalized" and "templated."

- **Wrong-class references are an instant spam flag.** Prospects pattern-match on surveillance language. One RED-class mention and the domain gets reported, the sender gets blocked, and the campaign's deliverability pays for it across every other prospect.
