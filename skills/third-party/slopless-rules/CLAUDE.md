# Global instructions

Example `~/.claude/AGENTS.md`. Keep `AGENTS.md` as the real file and `CLAUDE.md` as a symlink to it (`ln -s AGENTS.md CLAUDE.md`); edit `AGENTS.md`, since Edit and Write refuse to write through a symlink. Same convention in every project.

Every line below should change what the model does. Delete any line that would not cause a mistake if removed.

## Working

- Read the file before stating a fact about it. A memory, a handoff note or a prior summary is a hypothesis; check the artifact.
- Gate on the artifact a command produced (the file, the row, the URL), never on its exit code.
- Before reporting "none found", show the search can find a known positive. Never `2>/dev/null` a search you will draw a conclusion from.
- When numbers from two sources disagree, report both and the discrepancy.
- Before believing a surprising result, list the bugs in your own instrument that would produce it and test one. Checklists: `PREFLIGHT.md`.
- Never fill a gap with invented, placeholder or example data. Say the value is unavailable.
- Incremental by default: indexes, syncs, builds. Full rebuilds only on request or corruption.
- If an approach fails, read the error and test one focused fix before switching tactics.
- Proceed when you are about 90% sure what I want and state the assumption. Ask below that.

## Code

- Every changed line traces to the request. No drive-by reformatting, refactors or new abstractions.
- Match the existing style of the file, even where you would choose differently.
- Remove imports and variables your change made unused. Mention other dead code; do not delete it.
- Validate at system boundaries only.
- After any delegated Python edit, run `ruff check --select F821,F401` before the test suite.

## Safety

- IMPORTANT: never send an email or message, publish, post or deploy without showing the draft and getting an explicit yes that names the destination.
- No force push. No `rm -rf`; use `trash`. Ask before bulk operations.
- Secrets live in a secrets manager (`pass`, Keychain), never in plaintext files or commits.
- Before any destroy: back up, verify the backup as its own step, then destroy.

## Delegation

- Pass `model` explicitly on every Agent call.
- Delegate when the job is files with a writable acceptance check: 3+ files, 80+ lines, 5+ similar items, or 5+ shell or remote calls in a known sequence. Keep the spec, the diff review and the final check in the main thread.
- A delegate runs only the narrowest check that proves its own change. The parent runs the suite and the linter.
- Never ask a subagent to echo a large file into its reply. Edit in place, reply with a summary.
- Do not poll for a background job's output; the harness notifies you when it finishes.

## Shell

- `$?` after a pipeline is the last stage's status. Use `set -o pipefail` or `${pipestatus[1]}`, then still check the artifact.
- `rsync` dry runs need `-i` or they print nothing. Never pass `--delete` on an overlay copy.
- Quote heredoc delimiters (`<<'EOF'`) unless you want expansion.
- Python: `uv`, never `pip install --break-system-packages`.

## Writing

- No em dashes or en dashes (a personal preference, not an AI tell; see `rules/writing-voice.md`).
- No trailing summary after an action.

## Where the rest lives

- `rules/`: auto-loaded topic files. Put a rule that applies only to some files behind `paths:` frontmatter.
- `hooks/`: hard denies (`block-rm-rf.py`, `block-kill-pgid.py`), a formatter that runs only where the project configured one (`format-gate.py`), and a delegation nudge (`delegate-nudge.py`). Prefer a hook to a new rule here.
- `mods/`: `secrets-guard`, `read-first`, `rollback-notice`, `delegation-drift`.
- `METHOD.md`: the principles, cited by number. `PREFLIGHT.md`: read the one section that matches the moment.
