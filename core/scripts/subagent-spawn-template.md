# Subagent Spawn Template

Use this for every `sessions_spawn`. Fill in the bracketed fields. Tier the reasoning effort to the task (see AGENTS.md → Multi-Agent Orchestration).

## Tier selection
- **Scout** — read-only, narrow: locate a file, trace a code path, pull context, find tests. Light reasoning, parallel-friendly.
- **Worker** — scoped implementation: make a defined change, run checks, supporting work. Medium reasoning.
- **Smart worker** — hard/ambiguous: resolve ambiguity, coordinate help, difficult implementation. High reasoning.

## Brief template

```
TASK: [one-line objective]

TIER: [Scout | Worker | Smart worker]

CONTEXT: [what the coordinator already knows; what to cross-reference before acting]

OUTPUT: [exact deliverable — file path, format, or message]

WRITE SCOPE: [which files/dirs you may touch; everything else is read-only]

VERIFICATION: [how to confirm success — test, lint, row count, diff]

BOUNDARY: Complete this assignment directly. Do not spawn other agents; your parent's
delegation instructions apply only to your parent.

RESTRICTIONS (fresh-context agents don't inherit tool/safety boundaries — restate here):
- [e.g. compliant model only, no external sends, no destructive ops]

NO SILENT FAILURES: Log progress or raise. Never silently no-op. If blocked, report the
blocker + recovery path within [X] minutes.
```

## Coordinator checklist (spawning session)
- [ ] Cross-referenced — no duplicate investigation of work another agent/session already covered
- [ ] Tier matches task difficulty (don't over- or under-spend reasoning)
- [ ] Leaf boundary included
- [ ] Restrictions restated (fresh context inherits nothing)
- [ ] Timeout 30–60 min (quality over speed)
- [ ] Progress checkpoint expectation set (5–7 min interim ping; 30 min DIFF/VALIDATION/BLOCKER)
- [ ] Thread association captured BEFORE launch so results route back correctly
