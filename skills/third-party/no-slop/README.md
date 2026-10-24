# no-slop

**A prose linter that catches AI writing patterns. Based on [Wikipedia's Signs of AI Writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing).**

[![GitHub stars](https://img.shields.io/github/stars/Byk3y/no-slop?style=social)](https://github.com/Byk3y/no-slop)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Works with: Claude Code](https://img.shields.io/badge/Claude_Code-compatible-blue)]()
[![Works with: Cursor](https://img.shields.io/badge/Cursor-compatible-blue)]()
[![Works with: Codex CLI](https://img.shields.io/badge/Codex_CLI-compatible-blue)]()

---

## Before and after

**AI slop:**

> React Query is a groundbreaking library that serves as a pivotal tool in the modern frontend landscape. It seamlessly handles data fetching, caching, and synchronization, showcasing a meticulous approach to state management. The library boasts a vibrant community and has garnered significant adoption, underscoring its enduring value in the ecosystem.

**After no-slop:**

> React Query handles data fetching, caching, and background sync for React apps. You describe what data you need, and it handles refetching, deduplication, and cache invalidation. The community is large — over 40k GitHub stars — and most major React codebases have adopted it.

Same information. No slop.

---

## What it catches

| # | Rule | What it stops |
|---|---|---|
| 1 | Banned vocabulary | 40+ words like "delve," "tapestry," "pivotal," "vibrant," "leverage" |
| 2 | Simple copulas | Replacing "is/has" with "serves as," "stands as," "boasts" |
| 3 | Promotional tone | "Groundbreaking," "revolutionary," marketing-speak in technical writing |
| 4 | Vague attributions | "Experts say," "industry reports suggest" with no named source |
| 5 | Structural formulas | Rule of three, "not just X but Y," challenges-and-prospects endings |
| 6 | Participle chains | "-ing" filler: "highlighting," "showcasing," "emphasizing" |
| 7 | Elegant variation | Swapping synonyms for the same thing across sentences |
| 8 | Overstating significance | "Marks a turning point," "leaves an indelible mark" |
| 9 | Em dash overuse | More than one per paragraph |
| 10 | Collaborative language | "Let's explore," "as we can see," "we will examine" |
| 11 | Knowledge-cutoff disclaimers | "As of my last update," apologizing for gaps |
| 12 | Formatting excess | Over-bolding, emoji, title-case headings, "key takeaways" |
| 13 | Human writing habits | Contractions, varied sentence length, specifics over adjectives |

Every rule is sourced from [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), maintained by WikiProject AI Cleanup from observations of thousands of AI-generated texts.

---

## Install

### Claude Code (recommended)

```bash
# Clone into your skills directory
git clone https://github.com/Byk3y/no-slop.git ~/.claude/skills/no-slop
```

That's it. Claude Code auto-discovers skills in `~/.claude/skills/`. It will activate whenever you ask it to write prose.

You can also trigger it manually:

```
/no-slop
```

### Cursor

Copy the contents of [`agents/cursor.md`](agents/cursor.md) into your `.cursorrules` file at your project root.

### Codex CLI

See [`agents/codex.md`](agents/codex.md) for setup instructions.

---

## Usage

**Automatic**: Just ask your AI to write something — a blog post, email, PR description, documentation. The skill activates on its own for writing tasks.

**Manual**: Use `/no-slop` (Claude Code) to force-activate it when auto-detection doesn't kick in.

**What it does NOT activate for**: Code generation, short chat replies, commit messages. It only applies to prose.

---

## How it works

no-slop is a constraint skill, not a rewriter. It doesn't take your text and fix it after the fact. It teaches the AI what patterns to avoid *while writing*, so the first draft comes out clean.

The rules come from Wikipedia's article on signs of AI writing — a living document maintained by editors who review thousands of AI-generated texts. This isn't one person's opinion. It's a collaboratively maintained, evidence-based list of the patterns that give AI writing away.

### File structure

```
no-slop/
├── SKILL.md                # Core rules (13 constraints)
├── banned-vocabulary.md    # 40+ banned words with plain alternatives
├── examples/
│   ├── bad-examples.md     # Annotated AI-sounding text
│   └── good-examples.md    # Human-sounding rewrites
├── agents/
│   ├── claude-code.md      # Claude Code install guide
│   ├── cursor.md           # Cursor rules format
│   └── codex.md            # Codex CLI format
├── CONTRIBUTING.md
└── LICENSE
```

---

## Why no-slop?

| | no-slop | humanizer | anti-ai-slop-writing | avoid-ai-writing |
|---|---|---|---|---|
| Approach | Constraint (prevents slop) | Rewriter (fixes after) | Banned words | Tiered word replacement |
| Source | Wikipedia (evidence-based) | Wikipedia | Wikipedia + CMU | Mixed |
| Annotated examples | Yes (before/after per rule) | One example | No | One example |
| Conditional bans | Yes (context-aware) | No | No | No |
| Multi-agent | Claude Code, Cursor, Codex | Claude Code, OpenCode | 11+ agents | Claude Code, OpenClaw |

---

## Source

All rules are derived from **[Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)**, a collaboratively edited reference maintained by [WikiProject AI Cleanup](https://en.wikipedia.org/wiki/Wikipedia:WikiProject_AI_Cleanup). The article documents patterns observed across thousands of AI-generated texts by Wikipedia editors.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version:

- New banned words need evidence (link to Wikipedia article or published research)
- New examples need annotations explaining what's wrong and why the rewrite is better
- PRs should be focused — one rule or one example set per PR

---

## Star this repo

If no-slop made your writing better, [give it a star](https://github.com/Byk3y/no-slop). It helps others find it.

---

## License

[MIT](LICENSE)
