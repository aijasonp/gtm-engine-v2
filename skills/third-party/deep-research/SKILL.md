---
name: deep-research
description: >
  Performs in-depth, multi-step web research producing comprehensive reports with citations.
  Use when the user says "deep research", "research this deeply", "thorough research",
  "comprehensive research", "do a deep dive", or needs thorough analysis across multiple
  sources. NOT for quick fact lookups (use web_search instead).
---

# Deep Research Skill

Calls OpenAI Deep Research (Responses API with background mode) for comprehensive,
citation-rich research reports. Queries take 5-30+ minutes.

## When to Use

- Complex integration guides, multi-source technical analysis
- Questions where "check the docs" or a quick web search is insufficient
- Market research, competitive analysis, deep technical dives

**Don't use for:** Quick facts, simple questions, anything < 1 min.

## Prompt Quality Matters

Over-share context. The API won't ask clarifying questions.

Bad: "Research Swimlane API"
Good: "Research Swimlane SOAR integration. Cover: 1) API docs location, 2) Auth methods
with setup steps, 3) Key endpoints for case management, 4) Python/JS SDKs, 5) Webhooks,
6) Rate limits, 7) Code examples, 8) Edge cases and gotchas. Include inline citations."

## Models

| Model                   | Cost       | When to use                    |
|-------------------------|------------|--------------------------------|
| o4-mini-deep-research   | ~$0.50/q   | Default. General research.     |
| o3-deep-research        | ~$2.50/q   | Hardest problems only. 5x cost.|

## Usage — ALWAYS use sessions_spawn

Research takes 5-30 minutes. **Never poll in the main session** — it will time out.
Always spawn a sub-agent that runs the script and announces results when done.

```
sessions_spawn with task like:
  Run deep research:
  python3 skills/deep-research/scripts/research.py "<query>" -v -o docs/research/<topic>.md
  Then read the output file and present a summary of the key findings.
```

The sub-agent runs in isolation, writes the report to disk, and auto-announces
the summary back to chat. Main session stays responsive.

### Direct CLI (for manual/testing use only)

```bash
# Default model (o4-mini-deep-research)
python3 skills/deep-research/scripts/research.py "Your detailed query" -o output.md

# Use o3 for harder problems
python3 skills/deep-research/scripts/research.py "Your detailed query" --model o3-deep-research -o output.md

# Verbose (progress to stderr)
python3 skills/deep-research/scripts/research.py "Your detailed query" -v -o output.md
```

**API Key:** Reads from OpenClaw config at `skills.entries.openai-whisper-api.apiKey`
(shared OpenAI key). Override with `OPENAI_API_KEY` env var.

**Output:** Markdown report with executive summary, detailed sections, code examples,
citations, and source list. Saved to `-o` path or printed to stdout.

## Integration Notes

- **Long-running (5-30 min). MUST use sessions_spawn, never poll in main session.**
- Poll interval: 5s. Progress logged to stderr every 30s with `-v`.
- Reports go to `docs/research/` by convention.
- Sub-agent auto-announces completion — no manual checking needed.
