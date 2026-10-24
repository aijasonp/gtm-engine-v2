# TypeSafe AI (Jev) Integration — Reference

_Added 2026-09-21 (Jason Polanco). Core module: `scripts/outbound-engine/typesafe_client.py`_

## What Jev Is

System One model: fast structured decisions, not text generation. Send `state` + typed `questions`, get back typed `answers` with probability distributions and confidence. No parsing, no prompt engineering, no JSON-mode hacks.

- Endpoint: `POST https://api.typesafe.ai/v1/systemone`
- Model: `jev-latest` (currently jev-1.13.0)
- Price: **$0.042 per million INPUT tokens. Output tokens FREE.**
- Rate limits: 250K tokens/sec, 1,200 req/min (dynamic, can change)
- Context: 64K tokens/request total; 32K for state + longest question
- Latency: ~150-250ms per call (measured)
- SDK: `typesafe-sdk` v0.7.0 (pip). Reads `TYPESAFE_API_KEY` from env.
- Data: not trained on customer requests. ZDR available on enterprise.

## Three Primitives

| Type | Question | Returns |
|------|----------|---------|
| Choice | Which of these options? | `choice`, `probabilities`, `confidence` |
| Score | Which level on a rubric? | `score`, `legend`, `probabilities`, `confidence` |
| Noul | Is this true? | `noul` (0-1 probability) |

All questions in one call evaluate in parallel against the same state. Adding questions barely changes latency and costs only a few extra tokens. Ask everything you might need in one shot.

## Design Rules (from TypeSafe docs, validated)

1. **One snap judgment per question.** "Does this signal indicate active security evaluation?" is good. "Analyze this account" is not — decompose into atomic questions and combine in code.
2. **Composite scoring in code, not in the prompt.** Weight the answers yourself (see `composite_priority` in `score_icp_fit`). When priorities shift, change a coefficient, not a prompt.
3. **Confidence-gated routing.** High confidence → auto-act. Low confidence → human review. Every result has `needs_review` flag.
4. **Question IDs are for code only** — the model never sees them. Write the FULL question in `instructions`.
5. **Reference state fields by path** in backticks: `` `ticket.messages[0].text` `` when state is structured.

## The 4 Scoring Engines (typesafe_client.py)

### 1. ICP Scoring — `score_icp_fit()`
8 parallel questions: ICP fit (0-4 rubric), buying intent (noul), pain point (choice/7), industry fit (choice/10), company size (choice/5), AI adoption (noul), security pressure (noul), urgency (0-4 rubric).
Returns: `composite_priority` (weighted: 35% ICP, 20% intent, 15% AI adoption, 15% security pressure, 15% urgency) + `routing` (priority_outbound ≥0.7 / standard_outbound ≥0.5 / nurture ≥0.3 / disqualify) + `needs_review`.
Persist: `persist_icp_score(result)` → `account-knowledge/<domain>.md` § Jev ICP Score.

### 2. Reply Classification — `classify_reply()`
6 parallel questions: category (choice/12: interested, not_now, wrong_person, objection_pricing, objection_timing, objection_competitor, objection_need, unsubscribe, out_of_office, referral, hostile, other), buying intent (0-4), is_positive, is_unsubscribe, should_escalate, sentiment (0-4).
Returns: `action` (suppress / escalate_to_rep / notify_rep / defer / log_only).
Upgrade path for `smartlead_webhook_receiver.py` classification (currently basic POSITIVE/OBJECTION/OOO/NEGATIVE).

### 3. Signal Scoring — `score_signal()`
5 parallel questions: signal type (choice/11), relevance (0-4), buying intent, is_actionable, urgency (0-4).
Returns: `signal_quality` composite (35% relevance, 25% intent, 20% actionable, 20% urgency).
Persist: `persist_signal_score(result, domain)` → account-knowledge § Signal Log.

### 4. Account Enrichment Analysis — `analyze_account()`
7 parallel questions: AI maturity (0-4), security maturity (0-4), LLM deployment (noul), governance gap (noul), competitive landscape (choice/5), data quality (0-4), recommended angle (choice/7).
Persist: `persist_account_analysis(result)` → account-knowledge § Jev Account Analysis.

## Persistence (foundational rule: ALL results retained)

All scoring results write into `account-knowledge/<domain-slug>.md` via the persist_* functions. Sections are idempotent — re-scoring replaces the section, never duplicates. Signal scores append to the Signal Log (append-only per retention rules).

## Integration Points — ALL WIRED (2026-09-21)

1. **Clay ICP gating** ✅ — `clay_webhook_dispatcher.py` `_jev_icp_gate()` scores every account post-signal-scan, pre-dispatch. Routing: disqualify/nurture → skip, standard → dispatch, priority → dispatch + `jev_priority: true` in payload. Config: `icp_gating: true`. CLI: `--no-jev-icp`.
2. **Smartlead reply monitor** ✅ — `typesafe_reply_classifier.py` wrapper wired into `reply_monitor.py`, `lemlist_reply_monitor.py`, `smartlead_webhook_receiver.py`. Keyword fallback preserved. Config: `reply_classification: true`.
3. **Signal scanner** ✅ — `jev_signal_scorer.py` post-pass on `parallel_signal_scanner.py` output. Scores persist to account-knowledge via `upsert_signal(extra=...)`. Config: `signal_scoring: true`. CLI: `--no-jev`.
4. **Pre-call briefs** ✅ — `pre-call-brief.py` runs `analyze_account()` after HubSpot + account-store read. Results injected into Claude prompt as "JEV ACCOUNT ANALYSIS" section. Config: `precall_analysis: true`.
5. **Entity resolution** ✅ — `jev_entity_resolution.py` with CLI (`--dry-run`, `--limit`). Cron: weekly Sunday 03:19 UTC. Never auto-merges.

## Cost Reality (measured usage)

| Engine | Input tokens/call | Cost/call |
|--------|------------------|-----------|
| ICP scoring (8 questions) | ~1,337 | $0.000056 |
| Reply classification (6 questions) | ~845 | $0.000035 |
| Signal scoring (5 questions) | ~836 | $0.000035 |

At projected volume (~3,800 calls/month across all engines): **~$0.16/month.** Effectively free.

## Testing

```bash
cd ~/.openclaw/workspace
python3 scripts/outbound-engine/typesafe_client.py test          # ICP scoring
python3 scripts/outbound-engine/typesafe_client.py test-reply    # reply classification
python3 scripts/outbound-engine/typesafe_client.py test-signal   # signal scoring
```
