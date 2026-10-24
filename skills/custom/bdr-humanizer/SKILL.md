---
name: bdr-humanizer
version: 1.0.0
description: >
  ALWAYS apply when generating any outbound prospecting content for BDR/sales
  reps targeting net new pipeline — cold emails, LinkedIn DMs, follow-up
  sequences, or any outreach meant to generate meetings. Do not wait to be asked.
  This is the default standard for all AI-generated sales outreach. Detects and
  removes 30+ AI writing patterns, applies burstiness/perplexity injection,
  supports rep voice matching, and enforces sales-specific rules for cold email,
  LinkedIn DMs, and follow-up sequences.
license: MIT
compatibility: openclaw claude-code
allowed-tools:
  - Read
  - Write
  - Edit
---

## 1. What this skill does
Purpose-built for BDR and agentic revenue orgs. Detects and kills AI tells in cold emails, LinkedIn DMs, follow-up sequences, and broader sales outreach. Matches or mimics a specific rep's voice so scaled messaging still sounds like one human. Auto-adapts enforcement rules based on the outreach channel.

## When to Apply (Default Behavior)

This skill is **always on** for outbound prospecting content. Do not wait for the user to ask.

Auto-activate whenever generating:
- Cold emails or first-touch outreach
- LinkedIn connection requests or DMs
- Follow-up emails in a sequence
- Multi-touch outbound sequences
- Any message from a BDR/SDR attempting to generate net new pipeline

Do NOT apply to:
- Inbound reply drafts (unless asked)
- Internal communications
- Technical documentation
- Customer success / post-sale communications

## 2. Modes
- **rewrite (default)**: Detect every AI-ism, rewrite the content, and output the 4-section format defined in Section 13.
- **detect**: Scan only. No rewriting. Group findings by severity bands (P0/P1/P2).
- **polish**: Light intervention. Fix only P0 + P1 issues while preserving the provided voice.

## 3. Context Profiles
Auto-detect context from cues (email headers, LinkedIn handles, follow-up language). Allow explicit overrides via `context=<profile>`.

**cold-email**
- P0 + P1 enforcement at full strength.
- Promotional/salesy adjectives treated as high risk.
- Significance inflation is a credibility killer.
- Email body capped at 4 sentences.
- First sentence must be a specific observation (not a compliment).

**linkedin**
- Max 3 sentences per message.
- No pitch in the first touch.
- Relaxed: allow 1-2 emoji at line endings.
- Strict: enforce all vocabulary + structure bans.

**follow-up**
- Chatbot artifacts are P0.
- "Checking in" language is P0.
- Must cite the specific prior touchpoint.
- Must add new value (no bump emails).
- Max 2-3 sentences.

**sequence**
- Audit full multi-touch sequences for consistent voice.
- Flag repeating openers or mirrored structures across emails.
- Require each touch to have a distinct rhythm/structure.

**investor-email**
- Apply extra strict rules across all tiers.
- Any "thriving ecosystem" phrasing fails the message.

## 4. Voice Profiles
Pick or blend profiles to guide the rewrite. Default to context-specific voice (cold email vs LinkedIn) if none is provided.

**casual**: constant contractions, first-person POV, informal transitions ("So", "Look"), permission for fragments, parentheticals, and light humor.

**professional**: selective contractions, dry wit instead of jokes, concrete examples, short paragraphs (3-5 sentences max).

**warm**: heavy "we/our" language, empathy markers, shorter paragraphs, add personal context when relevant.

**blunt**: minimal words, no hedging, opinions treated as facts, active voice only, zero pleasantries.

**cold-email voice**
- First sentence = specific observation about prospect, never a compliment.
- Ban "I hope this email finds you well", "I wanted to reach out", "I'd love to chat/connect".
- One problem statement, one proof point, one CTA.
- Body limited to 4 sentences.
- Human sign-off (no "Best regards").

**linkedin-outreach voice**
- Ban "I came across your profile and was impressed".
- Start with a real observation or shared context.
- Max 3 sentences.
- No pitch in the first message.
- No hashtags.
- Must sound like a human DM.

**follow-up voice**
- Reference a specific prior touchpoint.
- Add new value (fresh info, resource, insight).
- Max 2-3 sentences.
- Ban "I wanted to follow up", "Just checking in", "Did you get a chance...".
- No groveling about how busy they are.

## 5. Rep Voice Matching
When writing samples are provided, capture the rep fingerprint before editing:
1. Measure sentence length distribution (short vs medium vs long).
2. Label word-choice register (casual, formal, slangy, jargon-heavy).
3. Note paragraph opening patterns (questions, statements, hooks).
4. Record punctuation habits (dashes, parentheses, ellipses, punchy periods).
5. Collect recurring phrases/verbal tics.
6. Observe transition styles between ideas.
Apply that fingerprint to the rewrite instead of default profiles. Invocation pattern: "Humanize this. Here's a sample of [rep name]'s writing: [sample]".

## 6. The 3-Pass Rewriting Process
#### Pass 1: Kill AI Vocabulary
- Replace every Tier 1 word immediately.
- Flag Tier 2 words when ≥2 appear in the same paragraph and replace or rewrite.
- Flag Tier 3 words only when density exceeds 3% of total words.

#### Pass 2: Break AI Structures
- Parallel negation ("Not X, but Y") → state the positive conclusion directly.
- Tricolons (lists of three) → cut to 1-2 items.
- Em dashes → zero tolerance; swap for commas or periods.
- Rhetorical Q+A → delete the question, keep the answer.
- Mirror structures (A then B with identical scaffolding) → break symmetry.
- Neat paragraph endings → let ≥30% end abruptly without tidy bows.
- Dramatic reveals ("Here's the thing:") → start with the substance.
- Significance inflation → state facts plainly.
- Uniform sentence length → force aggressive variation.

#### Pass 3: Add Human Texture (Burstiness + Perplexity Injection)
**Burstiness**
- Mix short (3-8 words), medium (12-20), long (25-40) sentences in each paragraph.
- Never allow 3+ consecutive sentences of similar length.
- Use fragments where helpful. One-word sentences welcome.

**Perplexity**
- Default to the 2nd or 3rd synonym, not the most predictable one.
- Add domain-specific jargon suited to the reader.
- Use informal transitions if the voice allows ("Anyway," "Look," "So here's the thing:").
- Drop unexpected but apt analogies tied to real experience.

**Human texture**
- Prefer specific details (numbers, names, dates, events) to vague claims.
- Let the author's opinion show.
- Leave some thoughts slightly unresolved.
- Begin sentences with "And" or "But" occasionally.
- Allow mild imperfections—avoid over-sanding.

## 7. Tiered Vocabulary Replacement Table
#### Tier 1 — Always replace
| Replace | With |
|---|---|
| delve / delve into | explore, dig into, look at |
| landscape (metaphor) | field, space, industry, world |
| tapestry | describe the actual complexity |
| realm | area, field, domain |
| paradigm | model, approach, framework |
| embark | start, begin |
| testament to | shows, proves, demonstrates |
| robust | strong, reliable, solid |
| comprehensive | thorough, complete, full |
| cutting-edge | latest, newest, advanced |
| leverage (verb) | use |
| pivotal | important, key, critical |
| underscores | highlights, shows |
| meticulous / meticulously | careful, detailed, precise |
| seamless / seamlessly | smooth, easy, without friction |
| game-changer / game-changing | explain what changed |
| utilize | use |
| watershed moment | turning point |
| marking a pivotal moment | state what actually happened |
| the future looks bright | cut |
| nestled | is located, sits, is in |
| vibrant | explain the activity or cut |
| showcasing | showing, demonstrating (or cut clause) |
| deep dive / dive into | look at, examine, explore |
| intricate / intricacies | complex, detailed |
| ever-evolving | changing, growing |
| enduring | lasting, long-running |
| actionable | practical, useful, concrete |
| impactful | effective, significant (or describe impact) |
| learnings | lessons, findings, takeaways |
| thought leader / thought leadership | expert, authority |
| best practices | what works, proven methods |
| at its core | cut |
| synergy / synergies | describe actual combined effect |
| interplay | relationship, connection |
| in order to | to |
| due to the fact that | because |
| serves as | is |
| features (verb) | has, includes |
| boasts | has |
| commence | start, begin |
| ascertain | find out, determine |
| endeavor | effort, attempt |
| embrace (metaphor) | adopt, accept, use |

#### Tier 2 — Flag when 2+ appear in same paragraph
harness, navigate/navigating, foster, elevate, unleash, streamline, empower, bolster, spearhead, resonate, revolutionize, facilitate, underpin, nuanced, crucial, multifaceted, ecosystem (metaphor), myriad, plethora, encompass, catalyze, reimagine, cultivate, illuminate, cornerstone, paramount, poised (to), burgeoning, nascent, overarching, transformative

#### Tier 3 — Flag only at high density (3%+ of total words)
significant, innovative, effective, dynamic, scalable, compelling, unprecedented, exceptional, remarkable, sophisticated, world-class

## 8. Sales-Specific Banned Openers (P0)
- "I hope this email finds you well"
- "I wanted to reach out because"
- "My name is [X] and I work at [Y]" (as opener)
- "I'd love to connect"
- "Just following up"
- "Did you get a chance to review"
- "I know you're busy, but"
- "Quick question"
- "Touching base"
- "Circling back"
- "Checking in"
- "Per my last email"
- "As mentioned"
- "Going forward"
- "I came across your profile and was impressed"
- "Hope this finds you well"

## 9. Sales-Specific Banned Closings (P0)
- "Please let me know if you have any questions"
- "Feel free to reach out"
- "Looking forward to connecting"
- "Hope to hear from you soon"
- "Best regards" / "Kind regards" / "Warm regards"
- "Thanks for your time and consideration"
- "Don't hesitate to reach out"
- "I'd love to hear your thoughts"
- "Looking forward to your response"

## 10. Sales P0 Credibility Killers
- Any banned opener/closing from Sections 8-9.
- Vague value propositions ("we help companies improve X" without specifics).
- Missing prospect specificity ("I noticed your company is growing" with no signal).
- Fake personalization ("As a leader in the [industry] space...").
- Chatbot artifacts anywhere in the copy.
- Em dashes.
- Significance inflation for routine claims.

## 11. Ghost Protocol Pipeline (BDR-adapted)
Use when generating net-new outreach (not just editing):
1. **Prospect Profile** — buyer, trigger signal, targeted pain, rep voice profile.
2. **Draft Generation** — draft with human pattern injection active from the start.
3. **AI Pattern QA** — scan all 30 patterns, flag survivors, score via rubric.
4. **Platform Adaptation** — format for email vs LinkedIn vs follow-up (line length, CTA placement, paragraph spacing).
5. **Polish Pass** — add 2-3 intentional imperfections to break statistical uniformity.

## 12. Quality Scoring Rubric
Score each dimension 1-10. Total below 35/50 requires revision.
| Dimension | Question |
|---|---|
| Directness | Are we making statements or padding with announcements? |
| Rhythm | Does the cadence vary or feel metronomic? |
| Trust | Does it respect the reader's intelligence? |
| Authenticity | Would someone believe a specific human wrote it? |
| Density | Is anything immediately cuttable? |

## 13. Output Format
**Rewrite (default)**
1. **Issues found** — bullet list of AI-isms with quoted text.
2. **Rewritten version** — clean draft with all fixes applied.
3. **What changed** — highlight major edits.
4. **Second-pass audit** — re-read and fix any surviving tells inline.

**Detect**
1. **Issues found** — grouped under P0 / P1 / P2.
2. **Assessment** — note which flags are definite problems vs judgment calls.

**Polish**
1. **Quick fixes** — list the P0+P1 fixes performed.
2. **Polished version** — lightly cleaned copy preserving voice.

## 14. Quick Reference Checklist
Run this before delivering any sales outreach:
- [ ] Any banned opener? Fix first.
- [ ] Any banned closing? Replace with something human.
- [ ] Em dashes? Remove them.
- [ ] Any Tier 1 words? Replace immediately.
- [ ] "Not X, but Y" structure? State Y directly.
- [ ] Three-item lists? Cut to one or two.
- [ ] Vague attribution? Name the source or delete.
- [ ] Significance inflation? State the fact without hype.
- [ ] Uniform sentence length? Inject variety.
- [ ] Generic conclusion? Make it specific or cut it.
- [ ] Fake personalization? Replace with a real signal or delete.
- [ ] Rubric score ≥35/50? If not, revise again.
