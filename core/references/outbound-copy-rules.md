# Outbound Copy Rules (PERMANENT — Jason mandates)

## No Em Dashes (Jason, 2026-08-07)
**Em dashes are banned from ALL externally-facing content, everywhere, always.** Applies to every email, LinkedIn message, subject line, Slack post, document, or any content created for or on behalf of any rep. No exceptions. No em dashes even as separators in subject lines.

Instead of em dashes:
- Clause continuation → use a comma or period + new sentence
- Before "{{CUSTOMER_D}}"/"{{COMPANY}}"/etc. elaboration → period, new sentence
- Subject line separator → use a colon ( : )
- Parenthetical aside → use parentheses ( ) or commas
- Before "without"/"not"/"no" → comma
- Between two independent clauses → semicolon or period

**Before delivering any content:** run a literal `—` search. If any em dash exists, fix it. No exceptions. This rule applies even when using templates or subagents.

## Banned Slop Phrases (Jason, 2026-06-30)
Never use:
- "If not, no worries" / "No worries at all" / "totally understand" / "I completely understand"
- "feel free to" / "Happy to show you"
- "Last one from me on this thread" / "Last note from me" / "Signing off on my end" / any AI "final email" opener
- "No hard feelings"
- Any sentence referencing {{COMPANY}} as if the RECIPIENT works at {{COMPANY}}
- Wishy-washy opt-out language that sounds like a chatbot apologizing

**Company name in body = PROSPECT'S company via `{{company_name}}`. Never "{{COMPANY}}" in email body.**

## No Fabricated Facts (Jason, 2026-06-30)
Never invent stats, incident details, or deployment quantities. Verified claims only:
- {{CUSTOMER_D}}: 34x ROI, 50-agent program, CISO runs it
- {{PARTNER_A}}: strategic partnership, 7 self-managed instances, deploying into 100 Fortune 500 customers
- {{CUSTOMER_A}}, {{CUSTOMER_B}}, {{CUSTOMER_E}}, {{CUSTOMER_C}}: named customers (no fabricated details)
- 9x YoY ARR growth, 145% net revenue retention, 26+ LLMs, on-prem/SaaS/air-gapped

Subagents hallucinate specific numbers — always fact-check their copy before uploading.

## Cold Email CTA Rules (Jason, 2026-06-22)
Never use: "Worth 15 minutes?", "Happy to show you", "I'd love to chat", time-specific asks.
Use instead: "Interested?", "Let me know if this resonates", "Curious to hear your take", "Open to hearing more?"

## AI4 Attendee Intelligence (Jason, 2026-06-29)
Reference `references/ai4-attendee-intelligence.md` for all new outbound:
- **Expanded ICP titles:** 76-80% of buyers aren't C-suite with "AI" or "Security" in title. Include Enterprise Architects, Directors of IT, Innovation leads, Platform Engineers.
- **Champion enablement:** 62% are influencers, not signers. Arm champions to build internal cases.
- **Openers:** "How many AI models is your org running?", "Who owns AI security?", "What's your board asking about AI risk?"
- **Vendor reality:** Most enterprises run 2-4 AI platforms. {{COMPANY}}'s multi-model governance maps directly.

## Palantir Sovereign AI (Jason, 2026-07-06)
Incorporate third-party sovereign AI validation (Palantir, NVIDIA) in all sequence writes and copy refreshes. Research at `references/palantir-sovereign-ai-intelligence.md`. Key: Alex Karp IP risk quote, Jensen Huang national security, "future of AI is on-prem." Palantir charges 8 figures; {{COMPANY}} delivers same governance at enterprise SaaS pricing.

## Content Writing Policy (Jason mandate 2026-06-30)
**Zero tolerance: all externally-facing content must pass the full anti-slop stack before delivery.**

Mandatory pre-draft:
1. **{{COMPANY}} Voice Prompt** — `references/company-voice-system-prompt.md` (Sections 0-4)
2. **{{COMPANY}} Brand Profile** — `skills/company-brand-engine/references/brand-profile.md`

Mandatory during drafting:
3. No-slop constraints — `skills/no-slop/SKILL.md` + `skills/slopless-rules/writing-voice.md`
4. Banned vocabulary — `skills/no-ai-slop-rossmann/skills/no-ai-slop/references/ai-writing-detection.md`
5. Banned CTA patterns — per Cold Email CTA Rules

Mandatory post-draft:
6. Pattern scan — `skills/avoid-ai-writing/SKILL.md` + `humanizer/SKILL.md` + `skills/humanizer-blader/SKILL.md`
7. Score 0-100 AI-tell. If >30, rewrite.
8. Ask: "What makes this obviously AI-generated?" Fix every tell.
9. If 5+ banned-vocab hits + 3+ structural patterns + uniform rhythm → full rewrite.

For outbound email sequences (additional):
10. Run `python3 skills/unslop/scripts/banned_phrase_scan.py` — must score <3 violations
11. Run `python3 skills/unslop/scripts/readability_metrics.py` — high sentence length variance

## Customer-Facing Commitments Need a Sourceable Action (adopted from {{OPS_AGENT}}, 2026-08-22)
Do not write "we're filing X" / "we're evaluating Y" / "we're shipping Z" in any customer-facing draft unless you can point to a verifiable artifact (Linear ticket, Slack commitment from someone with authority, or an active PR). Your own analysis recommending an action is NOT sourcing. For every "we will/are" sentence, ask "what's my source?" If you can't answer with a concrete artifact, either file the artifact first or drop the sentence. Internal follow-ups go to the human teammate, not the customer. ({{TEAMMATE_7}}, via {{OPS_AGENT}}.)

## Lemlist Campaign Copy + Approval (Jason mandate 2026-09-09)
**The GTM agent authors 100% of all campaign copy. Lemlist's AI copy generator is NEVER used.** There is no code path that calls it, and there never will be. Every subject line, body, follow-up, and LinkedIn invite is written by the GTM agent, run through the full anti-slop stack (steps 1-11 above), and only then pushed to Lemlist.

**No campaign is ever sent until Jason explicitly approves the copy.** Approval flow:
1. The GTM agent writes the copy and runs it through the anti-slop stack (must score <3 violations).
2. The GTM agent sends a test email to rep@example.com for EVERY sequence step via the Lemlist test-email path BEFORE activating.
3. Jason confirms the copy. No exceptions.
4. Only after explicit go does the GTM agent start the campaign.

**Never skip the humanizer/anti-slop pass.** If copy sounds AI-generated, it is not done. Rewrite until it reads human: varied sentence length, no em-dash overuse, no rule-of-three, no "peer conversation"/"genuine"/"worth the morning" filler, no third-person self-reference ("Aaron is a CISO"), real paragraph breaks. When in doubt, run the scanner and rewrite.

**Campaign state check (learned 2026-09-08):** Lemlist GET `status: draft` is the VALIDATION state, NOT the run state. Confirm run state via POST `/campaigns/{id}/pause` (200 `state:paused` = it was live) or POST `/campaigns/{id}/start` ("already running" = live). To stop a live campaign use POST `/campaigns/{id}/pause` (NOT PATCH — PATCH returns 405).

**Updating live step copy:** PATCH `/sequences/{seq_id}/steps/{step_id}` with `{"type":"email","subject":...,"message":...}` (the `type` field is required, else 400). The campaign-scoped path `/campaigns/{id}/sequences/steps/{id}` returns 405 — use the sequence-scoped path.

**Lemlist renders the message field as HTML — `\n` collapses to a space.** To get a real paragraph break after the greeting (and between paragraphs), use `<br><br>` in the message body, NOT `\n\n`. A `\n\n` in the stored copy renders as `Hi {{firstName}}, {{event_hook}} {{CUSTOMER_X}}...` all on one line. Always convert `\n\n` → `<br><br>` and `\n` → `<br>` before pushing to Lemlist (both in build scripts and when updating live steps).

References: `references/company-outbound-skills-catalog.md`

## Spintax + Deliverability Patterns (ported from coldoutboundskills review, 2026-09-21)

Source: external repo `growthenginenowoslawski/coldoutboundskills` (reviewed read-only, NOT installed). Full analysis in `deliverables/coldoutboundskills-review.md`. These are ADDITIONS to the rules above; they do not replace any existing rule. Where a ported rule conflicts with a Jason mandate above, the Jason mandate wins.

### Smartlead Spintax Rules

**Syntax:** `{option1|option2|option3}` — Smartlead picks one option at random per send, so no two emails are identical. This reduces pattern detection by spam filters. Spintax is Smartlead-native syntax, NOT Jinja/Liquid, so it does not violate the "only `{{variable_name}}` merge tags" rule in `references/smartlead-api.md`.

**Where to use it:** subject lines, openers/greetings, opt-out lines, CTAs, and transition words. Use 2-3 options per block.

**What to spin:**
- Always: greetings (`{Hey|Hi}`), opt-out lines, CTAs, transition words ("just", "also", "actually").
- When natural: verb choices (`{help|work with}`), sentence-level rephrasings.

**Never spin:** Smartlead variables (`{{first_name}}`, `{{company_name}}`, custom vars), signature placeholders (`%signature%`), specific data points (numbers, stats, brand names, pricing), and technical terms that must stay precise.

**The golden rule — no broken combinations:** Every combination Smartlead could randomly assemble must read as a natural, grammatically complete sentence. Make each spintax block a self-contained phrase so options don't depend on a nearby block. Instead of dependent blocks that can break (`{let me know if|would} {{name}} {would be better|be a better person}`), write each option as a full standalone phrase. When sentence structure makes independent blocks risky, wrap the whole sentence in one spintax block with full-sentence alternatives. After adding spintax, mentally walk every adjacent-block pairing; if any sounds off, restructure.

**Tone preservation:** All options must match the register of the original. If the original is casual, all options are casual. Don't mix `{Worth a shot?|Would you be amenable to a trial?}` — that's a register mismatch.

**⚠️ Spintax is a RANDOM chooser, not a conditional.** Never use spintax as an if-populated gate for a variable. `{Saw {{funding_line}}. |}` renders `Saw .` on empty rows about half the time and throws away the personalization about half the time. Instead of spintax-gating a variable, use a self-erasing variable (put the whole sentence in the variable so an empty value renders nothing) or split the list at upload time into populated/empty campaigns. Spintax is for wording variety only, never for conditional content.

### Spam-Word Additions (merged with our banned-slop rules, deduped)

Our existing rules already ban the slop phrases ("feel free to", "no worries", "happy to show you", etc.) and the AI-tell vocabulary (leverage, synergy, ecosystem, robust, etc.). The following are NEW deliverability spam-trigger words/phrases we did NOT already ban. Add these to the banned list; they are spam-filter triggers, not just AI tells.

**Banned single words (spam triggers):** `get`, `bank`, `credit`, `access`, `open`, `compare`, `problem`, `now`, `billing`, `deal`, `finance`, `financial`, `claims`, `insurance`, `mortgage`, `soon`, `new`, `performance`, `freedom`, `home`, `sales`, `medical`, `urgent`, `life`, `marketing`, `investment`, `diagnostics`, `friend`, `cash`, `invoice`, `extra`, `purchase`. Punctuation, hyphens, or splits do not make a banned token safe (`cash-cycle` is still `cash`).

**Banned short phrases:** `off chance`, `one time`, `all good`, `following up here`, `last note from me here`, `great fit`, `bumping this once`, `just following up once`, `circle back`, `one more quick follow-up`, `keep this open`, `compare notes`, `compare notes live`, `appreciate the reply`.

**High-risk promotional/pressure wording (banned):** `$$$`, `50% off`, `100% guaranteed`, `100% free`, `100% off`, `100% satisfied`, `access now`, `act fast`, `act immediately`, `act now`, `action required`, `affordable deal`, `amazing`, `amazing deal`, `amazing offer`, `apply here`, `apply now`, `avoid bankruptcy`, `bargain`, `best bargain`, `best deal`, `best offer`, `best price`, `best rates`, `big profit`, `bonus`, `buy now`, `buy today`, `call now`, `can't live without`, `cash bonus`, `cash out`, `claim now`, `claim your discount`, `click`, `click below`, `click here`, `click this link`, `contact us immediately`, `deal ending soon`, `discount`, `don't delete`, `double your money`, `double your wealth`, `drastically reduced`, `earn`, `earn cash`, `earn extra income`, `earn money`, `easy income`, `exclusive deal`, `expires today`, `extra cash`, `extra income`, `fantastic`, `fantastic offer`, `fast cash`, `final call`, `for free`, `free access`, `free consultation`, `free gift`, `free membership`, `free money`, `free quote`, `free trial`, `full refund`, `get it now`, `get out of debt`, `get started now`, `giveaway`, `great news`, `guaranteed deposit`, `guaranteed results`, `hurry up`, `important information`, `immediately`, `increase revenue`, `increase sales`, `incredible deal`, `instant earnings`, `instant income`, `instant savings`, `investment advice`, `join millions`, `limited time`, `lowest price`, `make money`, `million dollars`, `money-back guarantee`, `must read`, `no catch`, `no cost`, `no obligation`, `no strings attached`, `once in a lifetime`, `only $`, `only available here`, `order now`, `order today`, `please read`, `price protection`, `profits`, `promise`, `pure profit`, `quote`, `risk-free`, `satisfaction guaranteed`, `save $`, `save big money`, `save up to`, `sign up free`, `special invitation`, `special offer`, `special promotion`, `supplies are limited`, `take action now`, `the best`, `this won't last`, `thousands`, `time limited`, `today`, `top urgent`, `trial`, `unbeatable offer`, `unbelievable`, `unlimited`, `urgent`, `what are you waiting for?`, `while supplies last`, `why pay more?`, `will not believe`, `winner announced`, `wonderful`, `you are a winner`, `you will not believe your eyes`.

**Phishing/security-warning language (banned):** `access your account`, `account update`, `activate now`, `change password`, `click to verify`, `confirm your details`, `confidential information`, `data breach`, `download now`, `final notice`, `important update`, `immediate action required`, `install now`, `last warning`, `log in now`, `new login detected`, `password reset`, `payment details needed`, `phishing alert`, `security breach`, `security update`, `update account`, `verify identity`, `warning message`.

**Formatting bans (add to existing):** no ALL CAPS, no multiple exclamation marks, no fake urgency, no misleading subject lines, no excessive links.

**Unsubscribe/closeout line rule:** Never write an unsubscribe line that promises to stop following up based on silence — we DO follow up, that's the point of sequences. Instead of "I'll take silence as a no" / "read no reply as a pass" / "if I don't hear back I'll leave it here", write an action-conditional line: "A reply of 'no' / 'pass' is enough and I'll step out of your inbox", "Just say the word and I'll stop", "A one-word reply works fine if you'd rather I stopped". The user has to do something explicit for the sequence to stop; silence keeps the cadence running.

**Safe replacement patterns:** instead of `free consultation` → `open to a short conversation`; instead of `special offer` → `what we're seeing in the market`; instead of `act now` → `if relevant, happy to send details`; instead of `guaranteed results` → `this may be relevant depending on your situation`; instead of `click here` → `let me know and I can send it over`; instead of `limited time` → `not sure if this is timely for you`; instead of `increase revenue` → a precise business outcome.

### Per-Lead Sub-Agent Personalization Pattern (adapted to our Smartlead per-lead custom-vars)

We already do per-lead custom variables (situation/value/CTA lines pushed as Smartlead custom fields). What is genuinely NEW from their `personalization-subagent-pattern` is the **tune-then-scale approval loop** and the **strict 3-field output schema**. Adopt these:

1. **Tune before you scale.** Don't personalize 500 leads and then discover the prompt is wrong. Instead of fanning out immediately, run a sample on 1 lead, show the user the generated `situation_line`/`value_line`/`cta_soft`, collect edits, then run a batch of 10 with approval. Lock the prompt only after 2 consecutive rounds with zero edits, then scale to the full list.
2. **Keep the output schema to 3 fields max** (`situation_line`, `value_line`, `cta_soft`). Fewer fields = less that can go wrong. Map each to a Smartlead custom var (`{{situation_line}}`, `{{value_line}}`, `{{cta_soft}}`).
3. **Batch size 10-20 leads per sub-agent.** Bigger batches are cheaper but worse quality; smaller are higher quality but more context. For 1,000+ leads, run in rounds of 100 (10 sub-agents × 10 leads).
4. **Never ship a fabricated or thin-data line.** If a lead's `company_description` is missing or <20 chars, set the fields to null and use static copy instead. Filter out any field containing "cannot be generated" before upload.
5. **Spot-check 5 random leads per variant before upload** for repetition, factual errors, unnatural phrasing, and hedging. Add a "assert, don't hedge" rule if lines come out vague.
6. **This must still pass Jason's approval + test-email gate** (see Lemlist Campaign Copy + Approval above) and must NEVER reintroduce `{{personalization_line}}` (banned in `references/smartlead-api.md`). The tuned prompt replaces the Clay-AI-fabricated field with a human-approved one.

**Sub-agent prompt rules to enforce (port):** never fabricate facts (if thin, be general but not false); never use em dashes; never use "leverage", "synergy", "ecosystem", "world-class", "cutting-edge", "solutions"; never start `situation_line` with "I noticed" (overused); max ~20 words per field; assert, don't hedge.
