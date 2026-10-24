# {{COMPANY}} ICP Data System — v3

**Version:** 3.0 — Transcript-Validated, No Easy Outs
**Last updated:** March 29, 2026
**Owner:** RevOps / CRO

---

## Core Philosophy

Data quality comes from making shortcuts harder than doing it right.

1. **Call transcripts and notes are the primary source.** GTM agent reads every note and transcript and extracts ICP signals. Most fields are auto-populated — not manually entered.
2. **Forms collect only what transcripts can't reliably extract** — judgment calls, technical analysis, and post-close context.
3. **Every form answer is validated against the transcript.** If what you write doesn't match what was said, the GTM agent flags it and VP sees the inconsistency before verifying.
4. **No easy out loss reasons.** Selecting a soft reason ("went dark," "no response") requires providing specific dates and activity evidence that GTM agent checks against the HubSpot activity log.
5. **SE must have been on a call** for their section to count. SE input with no logged SE activity on the deal is flagged as unverified.
6. **New market requirements replace FedRAMP.** The relevant signal is whether a regulatory, compliance, or market requirement is blocking or driving the deal — not a specific product feature gap.
7. **Rep form completion is the last gate, not the first.** Deals don't wait for a form to move stages. Forms are required before data is counted in ICP analysis, not before stage advancement.

---

## Known Weaknesses of This Approach (and Mitigations)

Understanding where this system can fail helps RevOps and VP of Sales know where to focus attention.

| Weakness | Risk | Mitigation |
|---|---|---|
| Reps rush through forms with thin answers | Form data looks complete but is uninformative | Minimum character count on free text fields (50+ chars). The GTM agent detects generic answers across multiple deals from the same rep and flags. |
| "Went dark" / "No response" used as catch-all | Loss data still noisy | Selecting these requires: specific last contact date, number of attempts, and channel (email/phone/both). The GTM agent validates against HubSpot activity log. No activity logged = form rejected. |
| SE section filled without SE being on calls | Technical analysis is guesswork | SE section only counts as verified if SE has at least one logged call activity on the deal. Otherwise it's tagged `SE: Unverified`. |
| Transcript extraction misreads context | The GTM agent flags wrong field values | The GTM agent previews extractions to the rep in Slack before writing to HubSpot. Rep has 4 hours to correct. After 4 hours, it writes. |
| VP approves forms without reviewing transcripts | Verification is rubber-stamp | VP Verification Form surfaces the GTM agent's key transcript quotes alongside the form answers. VP can see: rep said X, transcript shows Y. |
| BDRs copy-paste the same "problem statement" | Handoff data is noise | The GTM agent detects identical or near-identical problem statements across multiple handoffs from the same BDR and flags to VP of Sales. |
| New market requirements underreported | Miss signals on where {{COMPANY}} can't go | Replaced FedRAMP-specific field with `New Market Requirements` field (see below). Selecting any option requires one supporting quote from the prospect. |
| Forms added late or after memory fades | Inaccurate recall | Post-Discovery Form auto-sends 2 hours after call. Close Form sends same day as stage change. Hard reminder at 24 hours if incomplete. |

---

## What the GTM agent Extracts From Transcripts and Notes

The GTM agent reads all call notes, activity logs, and connected transcripts and extracts the following. These write to HubSpot automatically — reps do not enter them manually.

| Signal | How Extracted | HubSpot Field |
|---|---|---|
| Buyer title and name | Intro and mention context | `Economic Buyer Title` |
| Primary pain | Most frequent problem mention | `Primary Pain` |
| Use case discussed | Product feature or scenario mentions | `Primary Use Case` |
| Current tool stack | Tool names and vendors mentioned | `Current Tools Mentioned` |
| Competitors referenced | Named alternatives in evaluation | `Competitive Alternatives Evaluated` |
| Deployment preference | Cloud / on-prem / self-managed language | `Deployment Preference` |
| AI maturity signal | Stage-of-adoption language | `AI Maturity` |
| Compliance and regulatory drivers | Framework names, regulatory language | `Compliance Drivers` |
| New market requirements | Gov, international, regulated industry context | `New Market Requirements` (see below) |
| POC signals | Pilot, POC, trial language | `POC Status` |
| Engagement quality | Depth and recurrence of engagement | `Qualification Confidence` |

The GTM agent previews all extracted values to the deal's assigned rep via Slack before writing. Rep has a 4-hour correction window.

---

## New Market Requirements Field

**Replaces:** `FedRAMP Required` checkbox

**Field type:** Multi-select + free text quote

**Purpose:** Capture whether a regulatory, compliance, geographic, or market-entry requirement is influencing the deal — either as a driver (they need governance) or a blocker (they need something {{COMPANY}} doesn't yet support).

**Options:**
- Federal / civilian agency requirement
- Defense / national security (CMMC, ITAR, classified)
- State or local government requirement
- International data residency (EU, Canada, APAC, etc.)
- Financial services regulatory (SEC, FINRA, OCC)
- Healthcare regulatory (HIPAA, HITRUST)
- Critical infrastructure / OT / ICS environment
- None identified

**Validation rule:** Selecting any option other than "None identified" requires a one-sentence supporting quote from the prospect. The GTM agent checks this quote against the transcript. If the quote does not appear in any logged activity, the field is flagged `Unverified` until VP confirms.

---

## Slack Forms — Design and Validation Rules

### Form 1: BDR Handoff Form

**Sent by:** GTM agent when a deal is created and assigned to an AE
**Filled by:** BDR
**Completion window:** 24 hours
**Validation:** GTM agent checks problem statement is unique (not copy-pasted from another handoff)

```
BDR HANDOFF — [Company Name]

1. How did this lead come in?
   [ ] Outbound — BDR sourced
   [ ] Inbound — website or content
   [ ] Partner referral
   [ ] Event / conference
   [ ] Executive referral

2. Who did you speak with?
   Name: ___________
   Title: ___________

3. What specific problem did they describe?
   (Required: 50+ characters. Be specific — "interested in AI security" will be rejected.)
   ___________________________________________

4. What exact words did they use when describing the problem?
   (Quote them directly if possible. This is validated against call notes.)
   ___________________________________________

5. Did they mention any tools, vendors, or AI they are currently using?
   ___________________________________________

6. Why did they agree to take a meeting? (What was the trigger?)
   ___________________________________________

7. ICP fit assessment:
   [ ] Strong fit — describe why in notes
   [ ] Possible fit — discovery needed
   [ ] Weak fit — taking the meeting anyway — explain:
   [ ] Not a fit — explain and flag for disqualification:
```

**The GTM agent validation:**
- Character count on fields 3 and 4
- Duplicate detection: same rep, similar answer across 3+ deals in 30 days
- Checks that contact exists in HubSpot with a logged call or email activity

---

### Form 2: Post-Discovery Form

**Sent by:** GTM agent, 2 hours after a call is logged on a deal in Initial Investigation or POC Planning
**Filled by:** AE (required) + SE (required only if SE attended the call — GTM agent checks activity log)
**Completion window:** 4 hours before the GTM agent writes extracted fields

```
POST-DISCOVERY — [Company Name]

--- AE SECTION ---

1. Economic buyer confirmed?
   [ ] Yes — Name: ___________ Title: ___________
   [ ] No — still at practitioner level — who was in the room? ___________
   [ ] Unknown

2. Budget signal?
   [ ] Budget confirmed — approximate range or ACV: ___________
   [ ] Budget TBD — what did they say about it? ___________
   [ ] No budget discussion yet

3. Deal temperature — what specifically makes you say this?
   [ ] Hot — reason: ___________
   [ ] Warm — reason: ___________
   [ ] Cold — reason: ___________
   [ ] Going dark — last real engagement date: ___________

--- SE SECTION (only sent if SE has a logged call activity on this deal) ---

4. Primary technical use case the prospect described:
   [ ] SOC alert triage and investigation
   [ ] AI governance / shadow AI control
   [ ] Incident response automation
   [ ] Threat intelligence workflows
   [ ] DevSecOps / AppSec
   [ ] Offensive security ({{PRODUCT}})
   [ ] IAM workflow automation
   [ ] GRC / Compliance audit prep
   [ ] Other — describe: ___________

5. Key integrations they mentioned needing connected:
   (Be specific — tool names. "Various security tools" will be flagged.)
   ___________________________________________

6. Competitors in the evaluation — what did they say about each one?
   (List competitor + what prospect said about them. Generic "mentioned 7AI" is flagged.)
   ___________________________________________

7. Technical fit assessment:
   [ ] Strong — their stack works, use case is clear — evidence: ___________
   [ ] Moderate — works with configuration — what needs configuring: ___________
   [ ] Weak — what's missing or misaligned: ___________
   [ ] Blocker — describe: ___________

8. Early fit signals (check only what you personally observed on this call):
   [ ] CISO or VP Security in the room and actively engaged
   [ ] Active SOC team — they described specific alert volume or pain
   [ ] AI governance gap stated explicitly by prospect
   [ ] Data sovereignty or on-prem requirement stated
   [ ] Compliance event creating urgency — which one: ___________
   [ ] Active POC or evaluation with a competitor underway
   [ ] None of the above
```

**The GTM agent validation:**
- SE section only sent if SE has a logged call on this deal. If SE section is submitted without a logged call, it's tagged `SE: Unverified`.
- Tool names in field 5 are checked against known integration list. Unknown tools are passed to RevOps as potential integration signals.
- Competitor mentions in field 6 are extracted and written to `Competitive Alternatives Evaluated` in HubSpot.

---

### Form 3: Close Form — Won or Lost

**Sent by:** GTM agent, immediately when deal is moved to Closed Won or Closed Lost
**Filled by:** AE (required) + SE (required) + CS (Closed Won only)
**Completion window:** 24 hours. At 12 hours incomplete: escalation to VP of Sales.
**Validation:** All key reason fields are cross-checked against transcript by the GTM agent before VP sees them.

```
CLOSE FORM — [Company Name] — [WON / LOST]

--- AE SECTION ---

1. In your own words, what was the primary reason this deal [closed / was lost]?
   (Required: 100+ characters. Specific. This is validated against transcripts and notes.)
   ___________________________________________

2. Economic buyer who signed or blocked:
   Name: ___________
   Title: ___________
   Were they in any calls logged in HubSpot? [ ] Yes [ ] No

3. POC or pilot conducted?
   [ ] Yes — use case validated (describe what was validated): ___________
   [ ] Yes — results inconclusive (what was missing): ___________
   [ ] No POC — why not: ___________

--- IF LOST ---

4. Loss reason — select the most accurate:
   [ ] Went dark — required: last contact date ___ number of outreach attempts ___ channel ___
   [ ] No response after outreach — required: dates and channels of all attempts ___
   [ ] No executive sponsor — describe what happened to the deal without one: ___________
   [ ] Lost to competitor — competitor name: ___ what did they offer that {{COMPANY}} didn't: ___________
   [ ] Budget not approved — who said it and when: ___________
   [ ] New market requirement we can't meet today — requirement type: ___ prospect quote: ___________
   [ ] Building internally — what are they building and with what resources: ___________
   [ ] Champion left — new contact if known: ___________
   [ ] Org change or freeze — describe: ___________
   [ ] Timing — come back when: ___ trigger to watch for: ___________
   [ ] Other — full explanation required: ___________

5. Should we re-engage?
   [ ] Yes — re-engage date: ___ who to contact: ___ what should change by then: ___________
   [ ] Monitor — watch for trigger: ___________
   [ ] No — reason: ___________

--- IF WON ---

4. What specifically closed this deal? (Check all that apply, add detail for each checked.)
   [ ] POC validated — what it proved: ___________
   [ ] Self-managed deployment was required — who required it: ___________
   [ ] Integration with a specific tool — which tool: ___________
   [ ] AI governance / data sovereignty requirement — what requirement: ___________
   [ ] Executive sponsor pushed it — who and what they said: ___________
   [ ] {{COMPANY}} beat a competitor — which one and how: ___________
   [ ] Other: ___________

--- SE SECTION (required on every close) ---

5. Technical use case delivered or evaluated:
   [ ] SOC automation [ ] AI governance [ ] IR acceleration [ ] Threat intelligence
   [ ] DevSecOps [ ] Offensive security [ ] IAM [ ] GRC / Compliance [ ] Other: ___

6. Key integrations connected or committed in writing:
   (List tool names. "Various integrations" is not accepted.)
   ___________________________________________

7. Technical win reason OR technical loss reason:
   (Required: 75+ characters. What specifically worked or didn't work technically?)
   ___________________________________________

8. Competitive technical positioning — what was decisive?
   (If no competitor: state that. If competitor: what was the deciding technical factor?)
   ___________________________________________

--- CS SECTION (Closed Won only) ---

9. What does the customer expect in the first 30 days?
   ___________________________________________

10. Who is the day-to-day contact post-close?
    Name: ___________ Title: ___________
    Is this the same person as the champion? [ ] Yes [ ] No — explain: ___________

11. Early risk signals:
    [ ] None — clean handoff
    [ ] Champion is not the day-to-day user — who is: ___________
    [ ] Technical deployment dependency not resolved — describe: ___________
    [ ] Executive expectations not aligned with product — what gap: ___________
    [ ] Other: ___________
```

**The GTM agent validation before VP form is sent:**
- AE loss reason is checked against transcript for at least one supporting mention
- "Went dark" requires HubSpot activity log to show at least 2 outreach attempts logged
- "No executive sponsor" requires no C-level or VP contact in the deal's activity log
- "Lost to competitor" requires the competitor name to appear in at least one note or transcript
- SE tool names are checked against known integration list
- SE technical reason character count enforced
- The GTM agent generates a summary for VP showing: stated reason vs. transcript evidence (supporting or contradicting)

---

### Form 4: VP of Sales Verification Form

**Sent by:** GTM agent, after Close Form is submitted AND after the GTM agent cross-validation is complete
**VP receives:** Close Form answers + GTM agent's transcript validation summary
**Completion window:** 24 hours

```
DEAL VERIFICATION — [Company Name] — [WON / LOST]

GTM agent Summary:
[Auto-generated: "Rep stated [X]. Transcript evidence: [supporting quote or 'No match found']."]
[Auto-generated: "SE stated [Y]. SE call activity: [confirmed / unverified]."]
[Auto-generated: "Competitor [Z] mentioned: [yes, in transcript on DATE / not found in transcript]."]

1. Close reason verified?
   [ ] Yes — accurate as submitted
   [ ] Partially — corrected reason: ___________
   [ ] No — actual reason: ___________

2. ICP Tier assignment:
   [ ] Tier 1 — strong fit, replicable profile
   [ ] Tier 2 — fit but not ideal
   [ ] Tier 3 — one-off, do not optimize for
   [ ] Disqualified — should not have been in pipeline

3. Qualification confidence:
   [ ] High — transcripts, notes, and form data are consistent
   [ ] Medium — some gaps but enough to count
   [ ] Low — thin notes, form answers not transcript-supported
   [ ] Ghost — no real engagement; exclude from ICP analysis

4. Coaching note for AE (required if Low or Ghost):
   ___________________________________________

5. Approved for ICP analysis?
   [ ] Yes
   [ ] No — exclude (reason: ___________)
```

---

## HubSpot Fields — Updated List

### Fields Reps Must Enter Manually

| Field | When |
|---|---|
| Deal Name | Creation |
| ACV | Creation |
| Close Date | Creation and updates |
| Deal Stage | Throughout |
| Associated Contact + Company | Creation |

All other fields are populated by the GTM agent extraction or Slack forms.

### New Fields (Auto-populated or Form-collected)

| Field | Source | Validation |
|---|---|---|
| `Primary Pain` | The GTM agent extraction | Rep preview before write |
| `Primary Use Case` | SE form or the GTM agent | SE call activity required |
| `AI Maturity` | The GTM agent extraction | Rep preview |
| `Deployment Preference` | The GTM agent extraction | Rep preview |
| `Competitive Alternatives Evaluated` | SE form + GTM agent | Transcript cross-check |
| `Current Tools Mentioned` | The GTM agent extraction | Rep preview |
| `New Market Requirements` | The GTM agent extraction + form | Supporting quote required |
| `Compliance Drivers` | The GTM agent extraction | Rep preview |
| `Economic Buyer Title` | AE form or the GTM agent | |
| `Champion = Economic Buyer` | AE close form | |
| `POC Status` | The GTM agent extraction + SE form | |
| `Key Integrations` | SE form | Tool name validation |
| `Technical Use Case` | SE form | SE call activity required |
| `Technical Win Reason` | SE close form | 75+ chars enforced |
| `Technical Loss Reason` | SE close form | 75+ chars enforced |
| `Competitive Technical Factor` | SE close form | |
| `Close Reason` | AE close form | Transcript cross-check |
| `Competitor Won` | AE close form | Transcript cross-check |
| `Reactivation Priority` | AE close form | |
| `Re-engage Date` | AE close form | |
| `ICP Tier` | VP verification | |
| `Qualification Confidence` | VP verification + GTM agent | |
| `Lead Source` | BDR handoff form | |
| `Data Source Completeness` | GTM agent (note count, transcript count) | |
| `GTM agent Validation Status` | The GTM agent post-close | Flags shown in VP form |

---

## Qualification Confidence Levels

Set by VP of Sales in the Verification Form. The GTM agent provides the evidence summary; VP makes the call.

| Level | Criteria | ICP Treatment |
|---|---|---|
| **High** | Substantive transcripts or notes present + form complete + transcript-supported close reason + VP verified | Included in all ICP analysis |
| **Medium** | Thin notes but some activity + form complete + VP verified | Included with confidence flag |
| **Low** | Form complete but no transcript support, or SE section unverified | Included with warning; excluded from win rate cohorts |
| **Ghost** | No substantive activity, form answers unsupported or absent | Excluded entirely; counted separately as a pipeline hygiene metric |

Ghost Deal rate is reported to the CRO monthly. A rising Ghost rate means deals are being created and pursued without real qualification signal. The target is under 10% of all closed deals.

---

## Role Responsibilities

### BDR Team

BDRs set the first ICP context. The BDR Handoff Form is required within 24 hours of booking a meeting. No form = no credit for the handoff in pipeline quality metrics.

**What changes from current state:**
- Problem statement must be specific and unique — generic answers are flagged and sent back
- Must log at least one call or email activity in HubSpot before the handoff form counts
- "ICP gut check" requires a reason for any answer other than "possible fit"

**BDR quality metric:** % of handoffs with verified Handoff Form (unique problem statement, logged activity, submitted on time). Target: 100%.

---

### Account Executive

AEs log calls and own deal hygiene. They do not fill in ICP fields — GTM agent handles that. Their job is to ensure every meaningful conversation is logged in HubSpot so the GTM agent has material to extract from.

**What changes from current state:**
- Every discovery or demo call requires a logged note in HubSpot within 4 hours (even a brief summary)
- Close Form loss reasons require specific evidence — soft reasons without activity backup are rejected
- "Went dark" requires documented outreach attempts in HubSpot activity log

**AE quality metric:** % of deals in POC Planning+ with at least one substantive call note per 14-day period. Target: 100%.

---

### Sales Engineer

SEs own all technical signal. Their form sections only count if they have a logged call activity on the deal.

**What changes from current state:**
- SE can no longer fill forms on deals they weren't involved in
- Technical win/loss reason requires 75+ characters — no one-word answers
- Integration lists must be specific tool names — generic answers rejected
- SE section is required on every Close Form, not optional

**SE quality metric:** % of deals past POC Planning with verified SE involvement (logged call + completed form section). Target: 100%.

---

### Customer Success

CS provides post-close health data that validates whether closed deals are actually Tier 1 quality.

**What changes from current state:**
- CS section of Close Form required within 48 hours of handoff notification
- 30/60/90 day health notes required in HubSpot — GTM agent prompts automatically
- CS flags early risk signals immediately, not at quarterly review

**CS quality metric:** % of won deals with CS close section and 30-day health note completed. Target: 100%.

---

### VP of Sales

VP verifies every close using the GTM agent's transcript summary alongside the form. Not a rubber stamp — VP is expected to override when form answers don't match transcript evidence.

**What changes from current state:**
- VP receives transcript evidence summary with every verification form
- Expected to override Qualification Confidence to "Ghost" when activity is thin, regardless of form answers
- Ghost Deal rate becomes a VP accountability metric — high Ghost rates indicate pipeline inflation

**VP quality metric:** % of closes verified within 24 hours + Ghost Deal rate (target <10%).

---

### RevOps

RevOps builds and maintains the system. Does not collect data.

**Setup (one-time):**
- [ ] Create all HubSpot custom properties
- [ ] Build HubSpot webhook to the GTM agent for activity triggers
- [ ] Configure form delivery via Slack at correct trigger events
- [ ] Build the GTM agent transcript extraction pipeline
- [ ] Build transcript cross-validation logic
- [ ] Build character count enforcement on key fields
- [ ] Build `New Market Requirements` field with supporting quote enforcement
- [ ] Build VP verification form with the GTM agent summary block
- [ ] Remove legacy manual required fields that are now form/extraction-covered

**Ongoing (weekly):**
- Review `GTM agent Validation Status: Flagged` deals (form says X, transcript says otherwise)
- Review missing form completions >24 hours old
- Ghost Deal audit

**Ongoing (monthly):**
- Form completion rates by rep, SE, BDR
- Qualification Confidence distribution
- Ghost Deal rate trend
- The GTM agent extraction accuracy spot check (sample 10 deals)

---

### Marketing Ops

Uses clean ICP data to sharpen lead scoring and campaign targeting. With `New Market Requirements` replacing FedRAMP, Marketing Ops can now segment campaigns by regulatory environment rather than a single product gap.

**Updated MQL criteria:**
- Map to Tier 1 ICP definition, updated quarterly by VP after verified closes
- Add `Primary Pain` and `AI Maturity` as scoring factors from BDR Handoff Forms
- Add `New Market Requirements = None identified` as a positive scoring signal for standard enterprise deals
- Use `Competitive Alternatives Evaluated` to segment content by competitive angle

**Monthly reporting:**
- MQL-to-SQL by source and Tier (Tier 1 only after 30+ verified closes)
- Content-sourced deals by `Primary Pain` topic
- New market requirement distribution across lost pipeline (signals where {{COMPANY}} needs to expand)

---

### CRO

Owns ICP definition. Reviews verified, transcript-supported data only.

**Monthly:**
- ICP Tier distribution of new pipeline
- Ghost Deal rate (data quality health check)
- `New Market Requirements` distribution in lost pipeline — where is {{COMPANY}} losing because of regulatory gaps?
- Reactivation Priority queue — executive outreach decisions

**Quarterly:**
- ICP Tier definition update based on VP-verified, transcript-supported data
- Technical win/loss patterns from SE sections
- Competitive win/loss analysis (transcript-validated)
- CS health data vs. ICP Tier — are Tier 1 wins actually succeeding post-close?

**Board metrics:**
- Tier 1 win rate (transcript-validated deals only)
- Ghost Deal rate as pipeline hygiene signal
- Competitive win/loss ratio (verified)
- New market requirement frequency in lost pipeline

---

## Win/Loss Review Cadence

### Weekly — VP of Sales + RevOps (30 min)

- All closes in past 7 days
- agent-flagged inconsistencies (form vs. transcript mismatches)
- Missing or late verification forms
- Ghost Deal audit

### Monthly — VP of Sales + RevOps + Marketing Ops (60 min)

- Close reason distribution (VP-verified, transcript-supported)
- ICP Tier distribution of new pipeline
- Ghost Deal rate trend
- Form completion rates by team
- Reactivation queue refresh

### Quarterly — Full GTM (90 min)

**Inputs:**
- RevOps: ICP cohort analysis (High + Medium confidence deals only)
- SE lead: technical win/loss pattern summary
- CS lead: post-close health by ICP Tier
- Marketing: MQL-to-SQL by Tier and source

**Agenda:**
1. What does a verified Tier 1 win look like? (data from High confidence closes) — 20 min
2. Top technical win patterns (SE-sourced) — 15 min
3. Top technical loss patterns and competitive signals — 15 min
4. New market requirements: where are we losing to regulatory gaps? — 10 min
5. ICP definition update — 15 min
6. Marketing and BDR alignment — 10 min
7. Actions — 5 min

---

## ICP Scoring

ICP Tier is assigned by VP of Sales in the Verification Form. No automated scoring until 30+ VP-verified, High-confidence closes exist.

Inputs VP uses:

| Signal | Tier 1 Indicator |
|---|---|
| Industry | Financial services, government, defense, healthcare, critical infrastructure |
| Company size | 500+ employees |
| Economic buyer | CISO, CIO, VP IT Security, Director Security Ops |
| Primary pain | Alert fatigue, AI governance, data sovereignty, SOC automation |
| AI maturity | Evaluating or formally using AI |
| Deployment preference | Self-managed interest present |
| Compliance driver | Any framework active |
| POC outcome | Use case validated |
| Technical fit (SE-verified) | Strong or Moderate |
| New market requirement | None (no blocker) or requirement is something {{COMPANY}} can address |

After 30 verified closes, RevOps runs empirical analysis to set data-driven Tier thresholds.

---

## Implementation Plan

### Week 1 — RevOps

- [ ] Create all HubSpot custom properties including `New Market Requirements`
- [ ] Remove legacy manual required fields
- [ ] Configure HubSpot webhooks for the GTM agent activity triggers
- [ ] Build character count enforcement rules

### Week 1 — GTM agent Configuration

- [ ] Build transcript/note extraction pipeline
- [ ] Build 4 Slack form templates with validation logic
- [ ] Build transcript cross-validation and inconsistency flagging
- [ ] Build VP verification summary generator (form + transcript evidence side by side)
- [ ] Build Ghost Deal detection and Qualification Confidence scoring

### Week 2 — VP of Sales

- [ ] Brief all reps, SEs, BDRs, CS on updated forms and validation rules
- [ ] Run one practice close cycle end-to-end
- [ ] First pipeline review with new Ghost Deal view

### Week 2 — Marketing Ops

- [ ] Update MQL criteria to reflect Tier 1 ICP definition
- [ ] Replace FedRAMP filter with `New Market Requirements` segment
- [ ] Update lead scoring with `Primary Pain` and `AI Maturity` signals

### Week 3 — All GTM

- [ ] Backfill BDR Handoff Forms for all currently open pipeline deals
- [ ] Ghost Deal audit: tag all current Closed Lost with no activity as Ghost
- [ ] SE audit: flag all deals past POC Planning with no logged SE activity

### Month 2

- [ ] First monthly win/loss review with clean data
- [ ] GTM agent extraction accuracy audit (10-deal sample)
- [ ] First Ghost Deal rate report to CRO

### Month 3+

- [ ] Quarterly review with full transcript-validated cohort
- [ ] Begin empirical ICP scoring if 30+ verified closes reached

---

*Last updated: March 29, 2026*
*Owner: RevOps / CRO*
