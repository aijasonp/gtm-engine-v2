<p align="center">
  <img src="banner.jpg" alt="Slopless" width="100%">
</p>

<p align="center">
  <a href="https://github.com/BioInfo/slopless/stargazers"><img src="https://img.shields.io/github/stars/BioInfo/slopless?style=flat&color=yellow" alt="Stars"></a>
  <a href="https://github.com/BioInfo/slopless/network/members"><img src="https://img.shields.io/github/forks/BioInfo/slopless?style=flat&color=blue" alt="Forks"></a>
  <a href="https://github.com/BioInfo/slopless/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://github.com/BioInfo/slopless/actions/workflows/test.yml"><img src="https://github.com/BioInfo/slopless/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="PRINCIPLES.md"><img src="https://img.shields.io/badge/principles-80-informational" alt="Principles"></a>
  <a href="#the-mods"><img src="https://img.shields.io/badge/Claude_Code-2.1.287%2B_mods-blueviolet" alt="Mods"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#the-method">The Method</a> &bull;
  <a href="#the-config">The Config</a> &bull;
  <a href="#the-hooks">The Hooks</a> &bull;
  <a href="#the-mods">The Mods</a> &bull;
  <a href="#the-anti-slop-system">Anti-Slop</a> &bull;
  <a href="#read-this-before-you-copy-anything">Read First</a>
</p>

---

> **An instrument that cannot fail certifies whatever you point it at.**

Every guard in this repo ships with tests in both directions, and the repo itself is built by a script that fails the build rather than publish something it cannot check. Try the guards in ten seconds, inside Claude Code:

```
/plugin marketplace add BioInfo/slopless
/plugin install secrets-guard@slopless
```

Claude Code configuration from daily use on real work. Not a tutorial. Not a summary. These are the actual files, generated from a live setup and sanitized for sharing.

Two layers, useful at different depths.

**The method.** 80 numbered principles for working with an agent that can be wrong confidently. Cite them in a review or a design doc without adopting any of the tooling. Every one was bought by a specific failure.

**The config.** The files you copy into `~/.claude/`. Rules, hooks, mods, settings, statusline.

## Read this before you copy anything

The most useful thing in this repo may be the reason to copy less of it than you expect.

In July 2026 Anthropic [removed over 80% of Claude Code's own system prompt](https://claude.dev/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models/) for Opus 5 and Fable 5, with no measurable loss on their coding evals. Their finding was that they had been overconstraining the model, and that on this generation the constraints cost more than they bought. Their guidance now: let the model use judgement, design interfaces instead of writing examples, and load context progressively rather than stuffing it all into one file.

There is a matching result in the other direction. In April 2026 Anthropic [added one line to that same system prompt](https://www.anthropic.com/engineering/april-23-postmortem), a length limit (*"keep final responses to ≤100 words unless the task requires more detail"*). Together with other prompt changes it hurt coding quality, one evaluation showed a 3% drop on both Opus 4.6 and 4.7, and they reverted it four days later.

Both results point the same way. **A standing rule is expensive and it is not free to add.** So:

- Prefer a hook to a rule. A hook fires; a paragraph hopes.
- Prefer a skill to a paragraph in `CLAUDE.md`. Skills load when relevant.
- Spend your `CLAUDE.md` budget on **gotchas a reader could not infer from the repo**, not on restating good practice.
- Audit for contradictions. Overlapping, conflicting instructions across your system prompt, skills and `CLAUDE.md` make the model burn reasoning reconciling them before it starts.
- Run `/doctor` in a Claude Code session. Anthropic built it to rightsize exactly these files.

Take the pieces here that solve a problem you actually have. Copying all of it wholesale is the failure mode this section is about.

## Quick Start

```bash
git clone https://github.com/BioInfo/slopless.git
cd slopless

# Pick and choose. Do not copy all of it by reflex.
mkdir -p ~/.claude/rules ~/.claude/hooks
cp rules/writing-voice.md ~/.claude/rules/     # anti-slop writing system
cp rules/code-style.md ~/.claude/rules/        # loads only when source files are in play
cp hooks/block-rm-rf.py hooks/block-kill-pgid.py hooks/exec_unwrap.py ~/.claude/hooks/  # hard guards
cp hooks/format-gate.py hooks/delegate-nudge.py hooks/websearch-year.py ~/.claude/hooks/  # optional
cp statusline.py ~/.claude/statusline.py
```

The guard mods install from inside Claude Code (2.1.287 or later):

```
/plugin marketplace add BioInfo/slopless
/plugin install secrets-guard@slopless
```

`settings.json` is included as a reference, not a recommendation. It grants `Bash(*)`, `Write(*)` and `Edit(*)` with `defaultMode: acceptEdits`, which suits a personal machine and is a poor fit for a managed work laptop. Read the `permissions` block before adopting any of it.

| Piece | Needs |
|---|---|
| `rules/`, `METHOD.md`, `PREFLIGHT.md` | any Claude Code version |
| `hooks/` | Python 3.10+, standard library only; tested on Linux and macOS |
| `mods/` | Claude Code 2.1.287+ |
| `statusline.py` | Python 3.10+, standard library only |

## The Method

| File | What it is |
|---|---|
| `PRINCIPLES.md` | All 80 principles, one line each. The reference card. |
| `METHOD.md` | The full canon, grouped into ten sections, with the reasoning. |
| `PREFLIGHT.md` | The checklists. What to run before you act, before you believe a result, before a claim leaves the session, before you publish. |

One sentence holds most of it:

> **An instrument that cannot fail certifies whatever you point it at.**

That is the shape of nearly every expensive mistake here. A dry run that prints nothing and exits zero. A freshness check reading a timestamp its own producer wrote. A test that type-checks a field nobody reads. A scan whose zero result was never positive-controlled. In each case the check ran, passed, and told you nothing, which is worse than no check because now you believe something.

The second sentence is about documents like this one:

> **Passive text loses to habit. A principle with no artifact has no enforcement.**

Which is why the hooks below matter more than the rules.

## The Config

```
PRINCIPLES.md          # 80 principles, one line each
METHOD.md              # the full canon
PREFLIGHT.md           # the checklists
CLAUDE.md              # an example global CLAUDE.md
CHANGELOG.md           # what changed in each release
rules/
  writing-voice.md     # anti-AI-slop writing system (100+ banned patterns)
  subagent-models.md   # the subagent output cap and what to do about it
  quality-gates.md     # verify before presenting, incremental over full
  operational.md       # API errors, liveness, shell traps that exit 0
  code-style.md        # path-scoped: no drive-by reformatting, edit the hunk
hooks/
  block-rm-rf.py       # hard deny on rm -rf
  block-kill-pgid.py   # hard deny on the kill -9 -$PGID footgun
  exec_unwrap.py       # shared: unwraps ssh / sh -c so guards see the payload
  test_public_guards.py # controls for both guards, in both directions
  format-gate.py       # runs a formatter only where the repo opted in
  websearch-year.py    # adds the current year to a search with no time anchor
  delegate-nudge.py    # nudges when delegable work is done inline
  test_delegate_nudge.py # its controls, both directions
mods/                  # guard mods, Claude Code 2.1.287+
  secrets-guard        # denies writes of secret files and credential-shaped content
  read-first           # recovers from "File has not been read yet"
  rollback-notice      # says a denied Bash call ran nothing; refuses commit -F /tmp
  delegation-drift     # counts inline calls since the last subagent; refuses poll loops
settings.json          # reference only, read the permissions block
statusline.py          # one line: git, model, context, usage limits, cost, cache
.claude-plugin/
  marketplace.json     # makes the mods installable with /plugin
.github/
  workflows            # CI: hook tests on Linux and macOS
```

## The Hooks

A rule is advice. A hook is a mechanism. These two are hard denies on `PreToolUse`, and they exist because both mistakes are unrecoverable.

**`block-rm-rf.py`** denies `rm -rf` in every spelling: `-rf`, `-fr`, `-Rf`, `-r -f`, `--recursive --force`, and after a `&&` or `;` or `|`.

**`block-kill-pgid.py`** denies `kill -9 -<pgid>`. The failure it prevents: on an orphaned process the PGID resolves to `1`, and `sudo kill -9 -1` kills every process on the machine. It is scoped to `kill` and deliberately does not match `pkill`, which would fire on every ordinary `pkill -f`.

**`exec_unwrap.py`** is the piece most guards are missing. A `PreToolUse` hook that reads only the outer command string never sees the payload inside a wrapper, so `ssh host "rm -rf /data"` and `sh -c 'kill -9 -1'` walk straight past a guard that looks correct. Both guards here unwrap first and scan the innermost payload.

**`test_public_guards.py`** runs 42 directed checks in both directions, then replays the Bash commands from your own Claude Code session transcripts through both gates. That second part is the one people skip: running only the deny cases proves a gate catches something and says nothing about what it wrongly catches, and an over-firing gate gets switched off, which lands in the same place as no gate at all. A fixture measures recall. Only real traffic measures precision.

```bash
python3 hooks/test_public_guards.py          # full, includes the traffic sweep
python3 hooks/test_public_guards.py --quick  # directed checks only
```

The full run prints up to five of your own commands that tripped a gate. They come from your session transcripts, so read them before pasting the output into an issue.

Wire them in `settings.json` under `hooks.PreToolUse` with matcher `Bash`.

**`format-gate.py`** (`PostToolUse`, matcher `Edit|MultiEdit|Write`) runs a formatter only where the repo opted in: a `.prettierrc`, a `prettier` key in `package.json`, a ruff config. It stops looking at the repo root, so a stray config in your home directory cannot opt every repo in. The failure it prevents is a three-line change arriving as a whole-file diff because a formatter ran at its defaults over a project with different ones. `python3 hooks/format-gate.py --selftest` runs its controls.

**`websearch-year.py`** (`PreToolUse`, matcher `WebSearch`) appends the current year to a query that names no year and no word like "latest", so a search for a library's docs does not come back with the version from two years ago. It returns the documented `updatedInput` field and carries every other input field over. A common version of this hook returns `modifiedToolInput`, which is not a hooks API field, so it silently does nothing. `python3 hooks/websearch-year.py --selftest` runs its controls.

**`delegate-nudge.py`** (`PostToolUse`, on edits and on Bash) counts delegable work done in the main session and nudges when it crosses a threshold without dispatching a subagent: 8 edits, one write of 150+ lines, or 10 remote and ops commands (`ssh`, `rsync`, `docker`, `systemctl` and similar). Thresholds are constants at the top of the file. Read-only commands do not count.

## The Mods

A hook sees one tool call and can allow it or deny it. A mod is a plugin of TypeScript function hooks (Claude Code 2.1.287 and later) that wraps the call, so it can run the tool, read the result, and change what the model sees next. Each mod here ships with its own tests, and the build runs them against the published copy.

A mod is code that runs with your permissions and is not sandboxed. Read the four here before you install them; together they are under 300 lines.

**`secrets-guard`** denies Edit, Write and NotebookEdit on secret locations (dotenv files, private keys, `~/.ssh`, `~/.aws`, `~/.gnupg`, the `pass` store) and on any content carrying a credential shape, including a password inside a URL. It also denies Bash writes to those paths and Bash reads that would print them. The allow cases came from real traffic the first version blocked: a `jq` path `.env.FLAG` and a stray `2>/dev/null` are not writes to a dotenv file.

**`read-first`** handles the engine's "File has not been read yet" error. On Edit it reads the file and retries once, which is safe because `old_string` must match exactly. On Write it does not retry: it returns the head of the file with the error and lets the model decide, because a Write would replace content the model never saw. It has not yet been seen to fire in live use.

**`rollback-notice`** fixes a misread that cost a real commit. When a `PreToolUse` gate denies a Bash call, nothing in that call ran, including the heredoc that was meant to write a file. The model tends to re-run only the half it cared about. This mod appends that fact to the denied result, and refuses `git commit -F` from the shared `/tmp`, where a concurrent session's stale file once became a commit message.

**`delegation-drift`** counts main-thread Bash, Edit and Write calls since the last subagent dispatch and nudges at every tenth. It also refuses a foreground `until`/`while ... sleep` poll loop, since the harness already notifies you when background work finishes.

```bash
claude plugin test mods/secrets-guard           # run one mod's tests
claude --plugin-dir mods/secrets-guard          # try it for one session
```

To load them every session, export `CLAUDE_CODE_PLUGIN_DIRS` as a colon-separated list of the mod directories.

## The Anti-Slop System

`rules/writing-voice.md` prevents AI-detectable writing through three layers.

**Banned words and phrases**, in twelve categories: LLM verbs (delve, leverage, utilize), hollow intensifiers (crucial, robust, seamless), abstract poetry (tapestry, journey, landscape), stock openings, performed reactions, faux-depth closers, mechanical transitions, and the rest.

**Structural anti-patterns.** Forced contrasts ("not only X, but Y"), rhetorical question scaffolding, reflexive rule-of-three, uniform paragraph length, dramatic upswings at paragraph ends, manufactured parallelism.

**Authenticity rules**, drawn from AI-text-detection research. Vary sentence length aggressively, at least one under 8 words and one over 20 per paragraph. Vary paragraph length from 1 to 7 sentences. Ground every assertion in something concrete. Pick words by connotation rather than probability.

The file is built to be forked: replace the voice section with your own patterns, keep the banned lists and anti-patterns, which are not personal.

## Model Routing

`rules/subagent-models.md` covers a gotcha that costs people a lot of time. **If every response stops at the same output-token count, look for a setting before you blame the harness.** A managed-settings file outranks every other scope, and a forgotten one that set `CLAUDE_CODE_MAX_OUTPUT_TOKENS` to 8,000 capped the main loop and every subagent on a personal machine for ten months. An earlier version of this README called that a fixed subagent limit. It was a config file nobody had opened.

The payload advice holds either way, because a hit cap is fatal on a thinking-only response: chunk writes to roughly 4K tokens, mandate incremental appends for file deliverables, and never ask a subagent to echo a large file back in its reply.

| Model | Best for |
|-------|----------|
| Haiku | File search, monitoring, lookups |
| Sonnet | Code generation, batch edits, analysis |
| Opus | Architecture decisions, complex planning |

## The Statusline

```
slopless ⎇ main* │ Opus · high │ ctx ▰▱▱▱▱▱▱▱ 18% 180.2k/1M ⟲500k │ 5h 24% ↻2h15m │ 7d 67% ↻3d11h │ $4.37 · $5.8/h │ cache 91% ♨50m
```

One line: directory and git state, model and effort, context used against the window and the auto-compact point, the 5-hour and 7-day usage limits with time to reset, cost and burn rate, and prompt-cache hit rate. It reads only fields documented on the [statusline page](https://code.claude.com/docs/en/statusline), needs no `jq`, drops segments from the right on a narrow terminal, and prints just the directory if the input is malformed.

## How this repo stays current

It is generated from a live `~/.claude`, not maintained by hand. A build script applies a reviewable list of transforms, then runs a deny-list scan that **fails the build** rather than stripping and continuing, because a silent strip produces a clean-looking artifact. The scanner is positive-controlled against planted strings on every run, the principle index is validated against the canon's own numbering, and the shipped guards must pass their controls after transformation before anything is written.

The guard mods pass their own tests on the built copy too, and a mod with zero tests fails the build. The file map in this README is checked against the tree, in both directions.

It still went four months stale once, which is why there is now a drift check as well. The hand-written files here (`CLAUDE.md`, `rules/`, `settings.json`, `statusline.py`, two of the hooks) are adapted, not transformed, so the build cannot regenerate them; it records which live source each came from and flags the file for review when that source changes.

## Philosophy

**Ship your config, not advice.** Actual files from a working setup.

**Hooks over rules.** A hook that fires beats a paragraph that hopes. Where a principle can be code, it should be code, because code is the only layer that cannot forget.

**Controls in both directions.** A gate tested only on the cases it should catch is half a control.

**Fewer standing instructions than you think.** See [the section above](#read-this-before-you-copy-anything). The vendor cut 80% of theirs.

## Contributing

Found a word or pattern that should be banned? Open an issue or PR. The list grows through real corrections.

## License

MIT

---

<p align="center">
  <sub>Built by <a href="https://x.com/builderleader">@builderleader</a></sub>
</p>
