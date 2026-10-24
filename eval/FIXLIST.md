# GTM agent Eval Fix List — 2026-09-23

Source: `reports/2026-08.md` + `reports/2026-08.json` (judge: claude-sonnet-4-6).
Owner: Jason Polanco. Target: raise Task Completion 0.81 → 0.95+, JSON Correctness 0.85 → 0.95+.

---

## P0 — Task Completion failures (weakest metric, 0.806)

### F1. Post-call briefs ship "Unable to generate summary" when transcript is missing
- **Evidence:** hubspot-note:0000000 ({{CUSTOMER_C}}, score 0.40), hubspot-note:0000000 ({{CUSTOMER_C}}, 0.60). Judge: "core components absent... brief falls well short of complete and actionable."
- **Root cause:** `post-call-brief-batch.py` line ~887: when no Zoom transcript / Granola note / HubSpot summary exists, prompt gets "No call summary was available" and the model writes an honest-but-empty brief (all MEDDPICC fields "Unknown").
- **Fix:** Instead of shipping an empty brief, add a data-recovery fallback chain + quality gate:
  1. Fallback chain already exists (Zoom → Granola → HubSpot notes) but gives up too early. Add: pull the HubSpot meeting/call engagement body + any linked emails on the deal in the ±3 day window as context.
  2. Quality gate: if final context < 200 chars of substance, DO NOT write the brief note. Instead, log to a "needs-transcript" list and DM the call owner asking them to paste notes or enable recording. An honest "I can't do this yet" beats a useless brief in the CRM.
  3. Track recovery rate: count briefs that shipped with real content vs aborted.
- **Files:** `~/projects/scripts/post-call-brief-batch.py`

### F2. Structured-write sessions run queries but return no data to the user
- **Evidence:** session:1e725065 (closed-lost reasons analysis, 0.50 + 0.55 — "script executed but produced no actionable results"), session:b6966168 (task associations, 0.60 — "provides the mechanism but does not demonstrate success").
- **Root cause:** these are MY working sessions — the judge saw tool calls without the final summarized answer in the sampled window. Partly a sampling artifact, partly real: long HubSpot pulls sometimes end with the data dumped into a file but no crisp human-readable summary in the thread.
- **Fix:**
  1. Behavioral rule (already in SOUL.md, needs sharpening): every data-pull task ends with a plain-English summary IN THE THREAD — counts, top findings, file path. Never end on a bare file write.
  2. Eval-side: widen the collector window for structured_write samples to include the session's final assistant message, not just the tool call. This is a collector fix in `monthly_eval/collectors.py`.
- **Files:** `projects/gtm-agent-eval/monthly_eval/collectors.py`, SOUL.md rule

### F3. Slack reply scored 0.75 — analysis delivered but spreadsheet never confirmed
- **Evidence:** session:a78fd35c (BlackHat lead prioritization, "final prioritized outreach spreadsheet was described as..." — output cut off).
- **Root cause:** same class as F2 — final deliverable link/summary missing from sampled output.
- **Fix:** covered by F2 fixes (collector window + always-close-with-summary rule).

---

## P1 — JSON Correctness failures (0.85)

### F4. Shell-script outputs counted as "structured writes"
- **Evidence:** session:b6966168 toolu_01E3bSW... scored 0.50 JSON correctness on a bash for-loop with curl — that's not JSON output at all, it's a script.
- **Root cause:** collector misclassifies exec tool calls containing `curl`/`json` as "structured JSON writes." The metric is grading the wrong artifact.
- **Fix:** tighten `collectors.py` structured_write filter: only count samples where the assistant's deliverable IS a JSON payload written to HubSpot/Linear (look for POST/PATCH body or hs_object write), not any exec containing JSON. This alone should lift JSON correctness toward 0.95 since the misclassified samples are the low scorers.
- **Files:** `projects/gtm-agent-eval/monthly_eval/collectors.py`

---

## P2 — Promptfoo regression suite (45 baseline failures)

### F5. Baseline model output violates house rules (em dashes, JSON fences, slop)
- **Evidence:** first promptfoo run: 10 pass / 45 fail across 12 requests.
- **Root cause:** the raw provider (gpt-5 via {{COMPANY}}) doesn't know {{COMPANY}} voice rules unless the prompt enforces them. Some of that is intentional (suite is a tripwire), but 82% failure means the PROMPTS themselves need the anti-slop system prompt baked in, mirroring production.
- **Fix:** add the {{COMPANY}} voice system prompt (references/company-voice-system-prompt.md) as a provider-level `prompt` prefix in promptfooconfig.yaml so the baseline reflects production prompting. Re-run, expect failure count to drop to the genuinely-hard cases. That becomes the true baseline.
- **Files:** `projects/gtm-agent-eval/promptfoo/promptfooconfig.yaml`

---

## Not started / blocked

### F6. Langfuse tracing — BLOCKED on docker install
- Docker not installed; no sudo; no elevated exec; rootless prerequisites missing. Needs {{ADMIN_1}} (or any admin) to `apt-get install docker.io docker-compose-v2` on agent-vm, then the build resumes (compose pull, secrets, seed, test trace — full runbook ready).
- **Ask:** flag to {{ADMIN_1}} with the one-liner.

---

## Status (updated 2026-09-23 21:35 UTC)

| Fix | Status | Result |
|-----|--------|--------|
| F1 post-call brief quality gate | ✅ DONE | Threshold raised 30→200 chars + substance signals (sentence count, pain/topic keywords). {{CUSTOMER_C}}-type empty briefs now skip + log instead of shipping. |
| F2 close-with-summary rule | ⏳ NEXT | Needs SOUL.md rule + collector window widening |
| F3 (same class as F2) | ⏳ NEXT | Covered by F2 |
| F4 collector misclassification | ✅ DONE | Structured-write collector now requires concrete write method + CRM endpoint + JSON payload. Read-only GETs, /search calls, association listings excluded. |
| F5 promptfoo baseline | ✅ DONE | 3 harness bugs fixed: (1) python asserts returned dicts instead of bools (35 false fails), (2) every test ran against all 5 prompts instead of its matching one (cross-prompt contamination), (3) isolation prompt missing em-dash rule + had "ARty" typo. Result: 45 fails → 0 fails. True baseline = 11/11 pass. |
| F6 Langfuse | 🚫 BLOCKED | Needs {{ADMIN_1}}: `apt-get install docker.io docker-compose-v2` on agent-vm |

## Priority order (remaining)
1. F2 (close-with-summary rule + collector window)
2. F6 (Langfuse — needs {{ADMIN_1}})
3. Re-run monthly eval in Oct to measure improvement
