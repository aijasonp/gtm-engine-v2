# {{COMPANY}} Marketing AI Team — RUNBOOK

This is the single document for triggering, managing, and reviewing the 7-agent {{COMPANY}} Marketing AI team.

---

## How to Trigger the Full Team

### Daily run (all agents, daily tasks only)
Tell the GTM agent in Slack:
> **"Run the daily marketing team"**

The GTM agent will execute all 7 agents in the daily sequence defined in `ORCHESTRATOR.md`. Outputs land in `.agents/outputs/[agent-name]/`.

### Weekly run (all agents, full weekly tasks)
Tell the GTM agent in Slack:
> **"Run the weekly marketing team"**

The GTM agent will follow the Monday–Friday sequencing in `ORCHESTRATOR.md`, respecting dependencies. Weekly run takes longer — GTM agent will update you when each agent completes.

---

## How to Trigger a Single Agent in Isolation

Tell the GTM agent in Slack using this format:
> **"Run the [agent-name] agent"**

Examples:
- `"Run the SEO & Content agent"` → daily scan + optional weekly tasks
- `"Run the CRO agent weekly task"` → runs only the weekly CRO checklist
- `"Run the Sales & GTM agent"` → produces sales assets, battle cards, pipeline review
- `"Run the Strategy agent"` → generates marketing ideas + priorities brief

For weekly tasks on a specific agent:
> **"Run the weekly [agent-name] task"**

---

## How to Review Outputs

All outputs are stored at:
```
~/.openclaw/workspace/.agents/outputs/
```

By agent:
| Agent | Output Folder |
|-------|--------------|
| Strategy | `.agents/outputs/strategy/` |
| SEO & Content | `.agents/outputs/seo-content/` |
| CRO | `.agents/outputs/cro/` |
| Content & Copy | `.agents/outputs/content-copy/` |
| Paid & Measurement | `.agents/outputs/paid-measurement/` |
| Growth & Retention | `.agents/outputs/growth-retention/` |
| Sales & GTM | `.agents/outputs/sales-gtm/` |

To review a specific output, tell the GTM agent:
> **"Show me the latest [agent-name] output"**
> **"Summarize this week's CRO audit"**
> **"What did the Strategy agent produce this week?"**

---

## Agent Instructions Location

Each agent's full instructions are at:
```
~/.openclaw/workspace/.agents/marketing-team/[agent-folder]/INSTRUCTIONS.md
```

Orchestration rules (run order, dependencies, DONE conditions):
```
~/.openclaw/workspace/.agents/marketing-team/ORCHESTRATOR.md
```

---

## Escalation

Agents run autonomously. The GTM agent only escalates to {{SALES_LEADER}} if:
- A blocker is encountered that requires human decision-making
- A budget decision is needed (ad spend, tooling, content production)
- A strategic pivot is recommended requiring executive input
- A logo customer shows churn signals

---

## Updating Agent Instructions

To modify what an agent does, edit:
```
~/.openclaw/workspace/.agents/marketing-team/[agent]/INSTRUCTIONS.md
```
Then tell the GTM agent: **"Update [agent-name] agent instructions"** with the change you want.

---

## Product Marketing Context

All agents read {{COMPANY}}'s brand and ICP context from:
```
~/.openclaw/workspace/skills/product-marketing-context/SKILL.md
```
Keep this file current. If {{COMPANY}}'s positioning, ICP, or proof points change, update this file first — all agents will automatically pick up the changes on their next run.
