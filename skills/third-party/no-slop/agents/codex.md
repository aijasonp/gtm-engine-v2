# Codex CLI

## Install

Add the no-slop rules to your Codex system prompt. Create or edit your `AGENTS.md` or system instruction file:

### Option 1: Clone and reference

```bash
git clone https://github.com/Byk3y/no-slop.git ~/.no-slop
```

Then add to your Codex instructions:

```
When writing prose, follow the rules in ~/.no-slop/SKILL.md
```

### Option 2: Inline rules

Add the following to your Codex system prompt or `instructions.md`:

```
# no-slop rules for prose writing

When writing any prose (docs, emails, READMEs, PR descriptions):

1. BANNED WORDS: Never use: delve, tapestry, pivotal, vibrant, meticulous, landscape (metaphorical), testament, underscore, intricate, interplay, garner, bolster, foster, showcase, emphasize, crucial, enhance, leverage, utilize, facilitate, streamline, robust (in prose), seamless, holistic, synergy, paradigm, ecosystem (metaphorical), groundbreaking, renowned, profound, comprehensive.

2. COPULAS: Use "is/are/has." Not "serves as," "stands as," "boasts," "features."

3. NO STRUCTURAL FORMULAS: No rule-of-three. No "not only X but also Y." No "challenges and future prospects" endings.

4. NO PARTICIPLE CHAINS: Cut "-ing" filler words (highlighting, showcasing, emphasizing).

5. NO PROMOTIONAL TONE: State facts. No hype. No vague attributions.

6. NO COLLABORATIVE LANGUAGE: No "let's explore," "we will examine."

7. FORMATTING: Minimal bold. No emoji. Sentence-case headings.

8. WRITE LIKE A HUMAN: Vary sentence length. Use contractions. Be specific.
```

## Update

```bash
cd ~/.no-slop && git pull
```
