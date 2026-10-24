# Cloudflare Clef Integration — Reference

_Added 2026-10-08 (Jason Polanco). Replaces TypeSafe AI (Jev). Core module unchanged: `scripts/outbound-engine/typesafe_client.py` — same 4 engines, same interfaces, new backend._

## What Clef Is

Cloudflare's open-weight (Apache 2.0) 27B decision model, System One / Jev-API compatible. Same primitives as Jev: state + typed questions (noul / choice / score) in, probability distributions per option out. Hosted on Workers AI — SOC2 Type II via Cloudflare's existing attestation (Jev had none; this was the swap driver).

- Endpoint: `POST https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/cloudflare/clef`
- Models: `@cf/cloudflare/clef` (27B) and `@cf/cloudflare/clef-flash` (low-latency). Select via request body `"model": "clef"` or `"clef-flash"`.
- Context: 64K (Jev was 32K). Multimodal: accepts up to 4 embedded images (PNG/JPEG/WebP).
- Price: $0.24/M input tokens, output free. At our ~3,800 calls/mo volume ≈ $1-5/mo. Effectively free.
- Max 64 questions per call, evaluated in parallel (same as Jev).
- Docs: https://developers.cloudflare.com/workers-ai/models/clef/
- Blog/benchmarks: https://blog.cloudflare.com/clef-decision-models/ (beats Jev on 7/10 decision benchmarks, up to 13x faster)

## Credentials

In `~/.openclaw/.env` (added 2026-10-08):
- `CLOUDFLARE_ACCOUNT_ID=<your-account-id>
- `CLOUDFLARE_AUTH_TOKEN=REDACTED_TOKEN` (scoped API token; verified live inference 2026-10-08)
- Note: `/user/tokens/verify` returns 1000/Invalid on this token class but `ai/models/search` + `ai/run` both work — scoped Workers AI token, not a Global key. Don't panic at the verify 401.

## Backend Switching — `TYPESAFE_BACKEND`

One env var controls the whole stack (in `.env` or exported):

| Value | Behavior |
|-------|----------|
| `jev` (default) | TypeSafe AI only. Legacy path. |
| `clef` | Cloudflare Clef only. All 4 engines run on Clef. |
| `shadow` | Jev primary (results returned to callers), Clef shadow. Agreement logged to `scripts/outbound-engine/output/clef-shadow.jsonl`. Clef failures NEVER break the pipeline. |

**FULL CUTOVER 2026-10-08 ({{TEAMMATE_2}} approved Clef over Jev; Jason directed immediate switch — no shadow period). `TYPESAFE_BACKEND=clef` in `~/.openclaw/.env`.** All 4 engines verified live on Clef post-cutover. ~~Jev key retained as rollback~~ → **Jev key REMOVED 2026-10-15 (Jason directed; Jev has no SOC2 — no fallback to a non-compliant vendor). `TYPESAFE_API_KEY` deleted from `~/.openclaw/.env` (backup at `~/.openclaw/.env.bak-pre-jev-removal-2026-10-15`). Clef is now the sole decision-model backend — no Jev rollback path.**

⚠️ **Two copies of the stack exist.** Live crons run from `~/projects/scripts/outbound-engine/` — `typesafe_client.py` there was synced with the workspace copy on cutover day (backup: `typesafe_client.py.bak-pre-clef` in that dir). Any future edit to `typesafe_client.py` must be applied to BOTH copies or the crons drift from the workspace.

## What Changed in typesafe_client.py (2026-10-08)

- `get_client()` now reads `TYPESAFE_BACKEND` and builds the right client. Return type is `TypeSafeClient`, `ClefClient`, or `_ShadowClient` — all expose `system_one(state=, questions=)`.
- `ClefClient` — drop-in replacement. Serializes the SDK's `Noul`/`Choice`/`Score` objects to Clef's wire format, wraps responses in `SimpleNamespace` so downstream attribute access (`.answers["x"].choice/.score/.noul`, `.confidence`, `.probabilities`, `.usage.input_tokens`) works unchanged.
- `_ShadowClient` — runs Jev primary + Clef shadow per call, logs per-question comparison (choice agreement, score/noul deltas, latencies, token usage) to clef-shadow.jsonl.
- `_env_or_file()` — all credential lookups now check env first, fall back to `~/.openclaw/.env`. Applies to both Jev and Clef keys.
- Zero changes to the 4 engines (`score_icp_fit`, `classify_reply`, `score_signal`, `analyze_account`), the persist_* functions, or any downstream caller. `industry_pass.py` and anything importing `get_client` picks up Clef automatically.

## Verified 2026-10-08

All against live Clef endpoint:
- ICP scoring (8 questions): passed. Routing/composite math intact.
- Reply classification (6 questions): passed. `escalate_to_rep` action correct.
- Signal scoring (5 questions): passed.
- Account analysis (7 questions): passed.
- Shadow mode: Jev primary 145ms / Clef shadow 498ms on same input, category agreed, per-question deltas logged.

## Clef vs Jev — response shape differences handled

- Clef wraps everything in `{success, result, errors}` envelope; `result.answers` matches Jev's answer map.
- Clef `score` answers include `legend` mapping index→label; Jev does too — passed through.
- Clef returns `usage.input_tokens`, `output_tokens: 0` always (output free, not counted).
- Clef question IDs allow letters/digits/`_`/`.`/`-` (max 100 chars) — our IDs all comply.

## Cutover — DONE 2026-10-08

{{TEAMMATE_2}} approved Clef; Jason directed full cutover same-day (shadow gate skipped by decision, not by accident). Post-cutover verification: all 4 engines passed on pure Clef (`get_client()` → `ClefClient`, live token counts confirm real inference), downstream imports clean (`clay_webhook_dispatcher`, `jev_signal_scorer`, `jev_reply_classifier`, `jev_entity_resolution`).

Shadow machinery remains available — set `TYPESAFE_BACKEND=shadow` anytime to resume Jev-vs-Clef comparison logging without code changes.
