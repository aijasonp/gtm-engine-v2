# Changelog

## v2.0.0 (2026-10-05)

The guards are now installable, and every hand-written file is checked against the setup it came from.

### Added

- **Guard mods, installable in one command.** `/plugin marketplace add BioInfo/slopless`, then install any of `secrets-guard`, `read-first`, `rollback-notice`, `delegation-drift`. They need Claude Code 2.1.287 or later. Each one ships with its own tests, and the build runs those tests against the published copy.
- **`rules/code-style.md`**, path-scoped so it loads only when a source file is in play: no drive-by reformatting, edit the hunk instead of the file.
- **`hooks/format-gate.py`** runs a formatter only where the repo opted in, and stops looking for that opt-in at the repo root.
- **`hooks/delegate-nudge.py`** nudges when a session does delegable work inline: 8 edits, one write of 150+ lines, or 10 remote and ops commands.
- **`hooks/websearch-year.py`** adds the current year to a time-free search query, using the documented `updatedInput` field.
- CI runs the hook tests in both directions on Linux and macOS.

### Changed

- `rules/writing-voice.md` is tiered by severity and density, gives a swap for almost every ban, and ends its check on a positive question as well as the subtractive ones. Em dashes are now treated as a style choice, not evidence of machine writing: human writers vary fiftyfold in how often they use them, and one published detector benchmark found them in 9.9% of human documents against 1.9% of machine ones.
- `rules/quality-gates.md`, `rules/operational.md` and `rules/subagent-models.md` carry the lessons from the last two months: the shell traps that exit 0, gates controlled in both directions, pass@k against pass^k, and how to brief a delegate.
- The method has 80 principles (P79, P80 are new). The README count is now generated, so it cannot drift.

### Fixed

- v1 said every subagent has a fixed 8,000-token output cap. That was wrong. The cap came from a managed-settings file nobody had opened, and it capped the main loop too. `rules/subagent-models.md` now says where to look.

### Upgrading from v1

Nothing you copied stops working. The hooks keep their names and wiring. `statusline.sh` is replaced by `statusline.py` (standard library only, no `jq`); the old script keeps working if you already copied it. If you copied `rules/subagent-models.md`, replace it: its central claim was wrong.
