# Code + Orchestration Rules

## Code Writing Policy
**All code written by a coding subagent. No Anthropic models. No OpenAI models. No exceptions — even minor changes.** ({{ADMIN_1}}, 2026-08-15, PERMANENT: "You shouldn't be using Anthropic or OpenAI models anymore for anything.") Spawn a coding subagent via `sessions_spawn` using a compliant model — default `together/moonshotai/Kimi-K3`, fallback `together/deepseek-ai/DeepSeek-V3`. Do not specify `openai/*` or `anthropic/*` model overrides in any spawn, cron payload, config, or script.

**Subagent timeout — quality over speed (2026-07-21):** Instead of tight 5–10 min windows (which produce shallow or incomplete results), set Codex and all subagent timeouts to 30–60 min minimum. A half-finished result costs more to fix than the extra agent time.

**Delegated-work progress rule (2026-08-26):** If 30 minutes pass without a DIFF/VALIDATION/BLOCKER checkpoint from a delegated subagent, post what you've tried and the recovery path. During CI/supervisor waits, surface visible progress within 15 minutes; for delegated work, send an interim ping at 5–7 minutes. A silent subagent is a stalled subagent — surface progress instead of waiting indefinitely.

**Supervisor checkpoint rule (2026-08-29):** Scheduled maintenance interruptions (token refreshes, heartbeat crons, health-monitor restarts) are NOT task phase changes. After handling them, resume the exact active pre-interrupt checkpoint — don't treat maintenance as progress toward the task or lose the checkpoint state.

## Multi-Agent Orchestration (adopted from {{OPS_AGENT}} via Codex Multi-Agent V2, 2026-09-08)
This is orchestration *behavior*, not a domain skill — lives here, not in a skill file. Tiered delegation + explicit coordination, applied to every `sessions_spawn`.

**Reasoning-tiered delegation (Scout/Worker/Smart-worker):** Match reasoning effort to the task, don't default everything to one level.
- *Scout* — read-only, narrow: locate a file, trace a code path, pull context, find relevant tests. Light reasoning, parallel-friendly.
- *Worker* — scoped implementation: make a defined change, run checks, supporting work. Medium reasoning.
- *Smart worker* — hard/ambiguous: resolve ambiguity, coordinate help, difficult implementation. High reasoning.

**Coordinator anti-duplication:** The spawning session is the coordinator. It assigns substantive work, avoids duplicate investigations, and tracks what each agent is doing. Cross-reference before acting (Context-Check Gate) applies to subagents too — never re-investigate what another agent already covered.

**Direct agent-to-agent handoff (when infra allows):** A scout that discovers something a worker needs passes findings straight to the worker instead of relaying through the coordinator. Only when the messaging infra exists — don't fake it with relay.

**Leaf boundaries (mandatory in every spawn brief):** Tell leaf workers: "Complete this assignment directly. Do not spawn other agents; your parent's delegation instructions apply only to your parent." Prevents runaway delegation chains.

**Definition of done + escalation (mandatory in every spawn brief, adopted from 0xMorlex Grok-agent guide 2026-09-15):** Every delegated task carries an explicit finish line and a stop-and-ask rule. An agent needs a job, not a personality — the prompt draws the responsibility boundary, the model supplies the intelligence. Two lines per spawn: (1) *what done looks like* — the concrete, checkable output that ends the task; (2) *what to do when unsure* — always "stop and ask," never "use best judgment" silently. A subagent with no escalation rule makes the call itself and you find out later. This pairs with the review gate: agents can prepare almost everything; humans approve the expensive mistakes.

**Fresh-context agents don't inherit tool/safety boundaries:** When spawning with fresh context (no fork), include essential restrictions directly in the assignment — don't assume the child knows them.

**No silent failures at the subagent level:** The no-silent-failures guarantee holds for delegated work too. Every subagent run logs or raises — never silently no-ops. A silent subagent is a stalled subagent (see Delegated-work progress rule).

## Linear Issue Description Format
Structure: Symptom (what's needed + who) → Component → Evidence (Slack/doc link) → Steps. Don't dump investigation logs. Additional context belongs in comments.

## Ticket Description Is the Source of Truth
When correcting a misframed ticket, rewrite the description directly — do NOT add a parallel "what changed and why" comment quoting the old framing. It reintroduces the confusion the correction cleared. The system keeps issue history server-side; the description is the single source of truth. (Hannah, 2026-05-20.)

## Campaign Build Status Tracking — Prevent Duplicate Work
Before building or uploading any new campaign, sequence, or Clay workbook, check the current build state. Parallel subagents and cron sessions may have already done the work. Mark status immediately when a build step completes — not after. "Campaign built but not verified" is NOT the same as "Campaign live." A stale or missing status entry causes duplicate builds.
Tracking doc: `output/campaign-build-status.md` (create if absent). Columns: Campaign | Workbook | Status | Last Updated | Notes.

## Transcript Sources — Always Check Both (Jason, 2026-07-17, PERMANENT)
Post-call briefs and demo call reviews MUST check both Zoom AND Granola for every call, every time. Never assume a call had no transcript based on one source alone. If Zoom recording was stopped or missing, Granola is the source of truth and vice versa. A "no transcript" note is only valid after both sources return nothing. Violating this = incomplete intelligence in HubSpot and wrong grades in call reviews.
