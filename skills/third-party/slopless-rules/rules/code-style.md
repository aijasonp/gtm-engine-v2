---
paths:
  - "**/*.{py,pyi}"
  - "**/*.{js,jsx,ts,tsx,mjs,cjs}"
  - "**/*.{go,rs,java,kt,swift,rb,php,c,h,cpp,hpp,cs}"
  - "**/*.{sh,bash,zsh}"
  - "**/*.{sql,tf,tfvars}"
---

# Code Style

**Path-scoped on purpose.** This file loads only when a source file is in play, so it costs nothing on a prose or ops session. Anthropic's memory docs put "code style and quality guidelines" in a CLAUDE.md-class file and say to make instructions "concrete enough to verify": `"Use 2-space indentation"` over `"format code properly"`. Everything below is written to that bar. A vague instruction here buys attention tax and no compliance.

Code written with this config goes into pull requests other engineers read. The reviewer is the audience.

## The one that gets a PR rejected

**Never reformat a line you were not asked to change.** No re-wrapping, no quote-style swaps, no import reordering, no trailing-comma sweeps, no renaming on the way past. If a file's existing style disagrees with your preference, the file wins.

A formatter run unconditionally is the usual culprit. A hook that ran `npx prettier --write` on every edited JS file applied prettier's 80-column default to a project written at about 120 columns, so touching one 113-line file produced a 48-line formatting diff, none of it related to the change. `hooks/format-gate.py` replaces that hook: it runs a formatter only where the project opted in, and says so when it acts. The rule stays here because the hook covers formatters and not judgement.

**A diff should read as one change.** If you cannot describe it in a single sentence without "and also", split it.

## Before you write it: the ladder

Read the code the change touches first, then stop at the first rung that holds: **(1)** does this need to exist at all · **(2)** already in this repo, so reuse it · **(3)** stdlib · **(4)** a native platform feature (`<input type="date">` over a picker lib, a DB constraint over app code) · **(5)** a dependency already installed · **(6)** one line · **(7)** only then, the minimum that works. Validation at trust boundaries, data-loss handling, security and accessibility are never on the ladder.

**A deliberate shortcut with a known limit gets a comment naming the limit and the upgrade trigger** (`# ceiling: global lock; per-account locks if throughput matters`). Without the trigger, a deferral quietly becomes permanent.

**Non-trivial logic (a branch, a parser, a money or security path) leaves one runnable check behind** if the repo has none covering it: the smallest assert or test that fails when the logic breaks. Trivial one-liners need none.

Borrowed from `DietrichGebert/ponytail`. Its agentic benchmark is Haiku 4.5 only, n=4: 54% fewer lines with no safety regression.

## Edit size

**Edit the hunk, not the file.** Rewriting a whole file to change three lines is where formatting drift and silent bugs enter, and it destroys the reviewer's ability to see what changed. Use `Edit` with a tight `old_string`; reach for `Write` only for a new file or a rewrite that was the request.

**Delete dead code rather than commenting it out.** Git holds the history.

**Do not add a dependency without saying so.** Name it, say what it replaces, and say why the standard library will not do.

## Moving code between modules

**★ A RE-EXPORT IS A SEPARATE BINDING, SO A MOVE ORPHANS EVERY TEST PATCH AIMED AT THE NAME.** `from newmod import thing` gives the old module its own name bound to the same object. `monkeypatch.setattr(oldmod, "thing", fake)` rebinds only the old module's name, so it reaches code that resolves `thing` from *that* module's globals and nothing else. Move the reader and the patch still applies, still raises nothing, and stops reaching: the test exercises the real thing while asserting against its fake. **`ruff --select F821,F401` cannot see this, because both modules are valid and every name resolves.**

**Before moving code out of a module, scan the test tree for the patch targets the move orphans.** Parse, do not grep. Collect every `monkeypatch.setattr(<mod>, "<name>")` under `tests/` and intersect it with the names the moved range **defines and also reads**, plus the names it **reads from outside**. Both shapes break. A name the range defines that only outsiders read is safe, because the outsider resolves the re-export. Repoint each orphan in the same commit as the move, and pin one with a control that asserts both directions.

The failure is silent in the dangerous direction. Extracting about 1,900 lines out of one module orphaned ten patch sites across two cuts, and the suite stayed green through all of them. One orphan was a suite-wide `conftest.py` stub that no-ops telemetry, so the tests would have written real rows to a live database; three more would have spawned real subprocesses in the real repo root. A hand-written name list caught three of the ten. Parse.

## What a reviewer will flag

Measured across 623 million code changes, 2023 to 2026 ([GitClear](https://www.gitclear.com/the_ai_code_quality_maintainability_gap)). These four moved most, so they are the four to check before handing work over.

- **Duplication.** Copy/paste within a commit is up 41% and duplicated 5-plus-line blocks are up 81%. Before pasting a block you already wrote, extract it or call the existing one.
- **Error masking.** Constructs that catch an error without evaluating its cause are up 47%. A bare `except: pass`, a `catch {}`, or `|| true` on a check turns a failure into a wrong answer. The operational half is the same: a collector with `try/except: return []` reports zero results while the source is blocked. A default is not data (P19, `rules/quality-gates.md`).
- **Reuse.** Cross-file function calls are down 35%. Search for the helper before writing a second one.
- **Legacy.** Changes to code untouched for a year are down 74%. Touching old code is normal work, not a special event.

## Comments

**Comment the trap, not the code.** Nine lines explaining why `which <tool>` lies during an `npx` run earn their place; one line restating what `spawnSync` does does not. Match the density of the file you are in.

**No section-banner comments, no changelog comments, no "// Step 1" narration.** If a function needs a map to read, it is too long.

## Before you hand it over

1. Run the project's own tests. Name the command and paste the result rather than asserting it passed.
2. Read your own `git diff`. Every line in it should be a line you meant to change.
3. If the diff contains formatting you did not intend, revert those lines before anything else.

**Verification is the most useful step available and it is not optional** (P38). Anthropic's best-practices doc says the same: *"Claude stops when the work looks done. Without a check it can run, 'looks done' is the only signal available."*

## Two calibrations

**A reviewer asked to find gaps will find some.** Anthropic's guidance, verbatim: *"Chasing every finding leads to over-engineering: extra abstraction layers, defensive code, and tests for cases that can't happen."* Fix what affects correctness or the stated requirement; leave the rest.

**Clean code does not make the agent more correct; it makes it cheaper.** A controlled minimal-pair study (arXiv:2605.20049, 660 trials on 6 repo pairs) found no significant pass-rate difference between clean and messy versions of the same repo, while clean cut token use 7-8% and **file revisitations 34%**. Messy code does not make the agent fail; it makes it search. That is the self-interested argument for the rules above, separate from the reviewer.

## Put the repo's daily commands in its own `AGENTS.md`, with quiet flags

Every command Claude runs appends its output to the conversation, and that output is re-sent on every turn after. A test runner that prints 400 passing lines one at a time costs that for the rest of the session.

**When you learn a repo's build/test/lint command, write it into that repo's `AGENTS.md` the same session, in the exact form you would type it, quiet flags included:** `npx vitest run <file> --reporter=dot`, `uv run pytest -q <path>`, `npm run lint -- --quiet`. It saves a discovery turn and a few hundred lines of output in every session after it.

**Do not invent one.** A repo that is not test-runner-centric may have nothing true to write. A wrong command in an `AGENTS.md` is worse than none, so verify it runs before you record it.
