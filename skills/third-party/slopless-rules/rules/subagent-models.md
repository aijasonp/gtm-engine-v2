# Subagent Model Selection

When using the Agent tool, always pass the `model` parameter explicitly.

## An output ceiling is a settings fact, so read the whole cascade first

**If every response stops at the same token count, look for a setting before you blame the
harness.** A managed-settings file (`/Library/Application Support/ClaudeCode/managed-settings.json`
on macOS, `/etc/claude-code/managed-settings.json` on Linux) outranks every other scope. One
that set `CLAUDE_CODE_MAX_OUTPUT_TOKENS` to `8000` was root-owned and forgotten on a personal machine for ten months
and capped the main loop and every subagent alike, on every model. Earlier passes missed it
because they read only the user-level value.

Two things make this hard to test. The `env` block in `settings.json` overrides the inherited
shell, so `VAR=x claude ...` is not a valid control; pass `--settings '{"env":{...}}'`
instead. And `usage.output_tokens` from `claude -p --output-format json` is a sum across
responses, so read per-response counts from `--output-format stream-json`.

A hit cap is survivable on text, because a retry emits new prose. On a thinking-only
response it is fatal: the retry emits nothing and runs out of attempts. A bigger model
changes neither case.

**Bound the payload, not the call count.**

- Chunk writes to roughly 4K tokens each.
- Any agent whose deliverable is source or data files gets incremental writes mandated in
  the opening brief: skeleton first, then appends of about 150 lines.
- Never tell a subagent to echo a large file back in its reply. Have it edit in place and
  return a summary plus a verification command.
- An agent with no write tool fails quietly here. A long report truncates into a short,
  plausible answer rather than an error, so brief it to deliver labelled chunks.

Reasoning effort is not free either. Drop it for mechanical producer work, keep it for
judgment.

## When to delegate

Delegate when the job is bigger than its spec: the deliverable is files in a repo, you can write
the acceptance check first, and it clears 3 or more files, 80 or more lines, 5 or more similar
items, or 5 or more shell or remote calls with a known sequence. Work inline when the task is
iterative, a judgment call, architecture, or writing in your own voice. Keep the spec, the
route, the `git diff` review and the gate in the main session. `hooks/delegate-nudge.py` counts
these shapes and nudges when a session crosses them without dispatching.

## Writing the work order

- **The delegate edits and runs only the narrowest check that proves its own change. The parent
  owns the test suite, the linter and the `git diff` review.** A brief thick with gates spends
  the delegate's turn budget on verification: one agent edited nothing before its ceiling, and
  the re-dispatch with gates stripped came back with broken code the parent had to catch.
- **After any delegated Python edit, run `ruff check --select F821,F401` before the suite and
  before believing the report.** A passing suite is not this check: 1,570 tests passed over a
  module with four calls to an undefined name, because those branches never ran.
- **A test of a safety property (a refusal, a cap, a gate) must come with the line the delegate
  mutated to make it fail, and the failing output.** "Assert both directions" was once satisfied
  by `len("x"*257) > 256` standing in for "the cap fires", a test that never called the function.
- A job of N bespoke bodies wants one file per dispatch, not N in one.
- A sequence of shell or remote calls with a known plan is delegable too. The moment discovery
  ends and execution begins is the dispatch point. Each step in the brief gates on the artifact.

## While it runs

- **An absent artifact from a job that is still running is not a failure.** The harness tells
  you when a background agent finishes. A mid-flight check for its output file can only return
  "absent" while the work is fine; one fork was declared dead at six minutes and then returned
  a full report.
- An agent file written mid-session is not dispatchable in that session. Agents are read at
  session start, so the first use fails with "not found".

## Decision rule

1. Simple search, read, lookup, bulk ops -> `haiku`
2. Code writing, analysis, multi-step reasoning -> `sonnet` (default for most work)
3. Architectural judgment, complex tradeoffs, anything written in your own voice -> `opus`

## Quick reference

| Model | Best for |
|-------|----------|
| haiku | File search, cost checks, monitoring, parallel exploration |
| sonnet | Code generation, batch edits, test writing, document creation |
| opus | Architecture decisions, research synthesis, complex planning |
