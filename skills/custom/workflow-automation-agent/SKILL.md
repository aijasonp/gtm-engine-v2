---
name: workflow-automation-agent
description: Decomposes a high-level outbound or GTM goal into a concrete, tool-mapped, step-by-step workflow. Produces execution plans for automated sequences, signal-to-outreach pipelines, and BDR process design — no vague strategy, only actionable steps with owners and tools assigned.
---

# Workflow Automation Agent

## Overview

"Build an automated outbound sequence" is a goal, not a plan. This skill takes any GTM or outbound objective and produces a concrete workflow: discrete steps, tool assignments, decision points, data flows, and handoff logic.

Output is always execution-ready — something an AE, RevOps engineer, or GTM agent can act on immediately.

---

## Instructions

### Inputs
Provide:
- **Goal:** What outcome does this workflow achieve? (e.g., "Auto-enroll new inbound leads into a 5-touch sequence")
- **Trigger:** What starts the workflow? (e.g., new HubSpot contact, Clay enrichment complete, meeting booked, deal stage change)
- **Persona:** Who is the target? (title, company type, known pain)
- **Tools available:** Which systems are in play? (HubSpot, Clay, Slack, LinkedIn, the GTM agents)
- **Human touchpoints:** Where does a rep need to approve, review, or take over?

### Output format

**WORKFLOW: [Name]**  
*Goal: [one sentence]*  
*Trigger: [specific event]*  
*Owner: [Agent / AE / RevOps]*

---

**Step-by-step flow:**

| # | Step | Tool | Owner | Decision/Logic |
|---|------|------|-------|---------------|
| 1 | [Action] | [Tool] | [Human/Agent] | [If/then or always] |
| 2 | ... | | | |

**Data inputs required:**
- [Field 1]: sourced from [System]
- [Field 2]: sourced from [System]

**Human approval gates:**
- Step [X]: Rep reviews [output] before [action] fires
- Step [Y]: Manager approves [threshold] before sequence launches

**Exit conditions / error handling:**
- If [condition], workflow pauses and alerts [owner]
- If [data missing], step falls back to [action]

**Success metric:**
- How do we know this workflow is working?

---

### Standard BDR Workflow Templates

When the goal matches one of these, use the template as a starting point and customize:

**Template A — Signal-to-Sequence**
Trigger: Hiring signal / funding event / tech install detected  
1. Agent detects signal via research  
2. Agent enriches account (Deep Research Synthesizer)  
3. Agent scores urgency (Hot/Warm/Cold)  
4. If Hot: draft personalized email using SCQA framework → queue for rep review in Slack  
5. Rep approves or edits → email sends from HubSpot  
6. Sequence continues (follow-up 3, 7, 14 days) or pauses on reply  

**Template B — Inbound Lead Fast-Follow**
Trigger: New contact fills demo form  
1. HubSpot creates contact  
2. Agent pulls company research brief (Deep Research Synthesizer)  
3. Agent identifies likely ICP fit and assigns intent score  
4. High-fit: Rep notified in Slack with brief + suggested opener  
5. Low-fit: Auto-enroll in nurture sequence  
6. Rep logs call notes → Agent drafts follow-up  

**Template C — Stale Deal Reactivation**
Trigger: Deal with no activity > 14 days  
1. HubSpot activity check fires (weekly)  
2. Agent pulls deal context + last activity  
3. Agent drafts reactivation email using SCQA (Complication = time passing / change in their landscape)  
4. Rep reviews + sends  
5. No response in 7 days → escalation prompt to AE  

**Template D — Post-Call Follow-Up Automation**
Trigger: Call logged in HubSpot  
1. Agent reads call notes / disposition  
2. Agent drafts follow-up email: recap + next steps + relevant resource  
3. Agent creates HubSpot task for agreed next action  
4. Rep reviews + sends within 2 hours  

---

## Constraints

- Every step must have a named tool or owner. "Someone does X" is not a workflow step.
- Human approval gates are mandatory before any external communication fires (email, LinkedIn message, call).
- Workflows must have explicit exit conditions — what stops the automation if something goes wrong.
- Do not design workflows that depend on tools not yet configured. Flag dependencies clearly.
- If the goal is too vague, ask clarifying questions before producing a workflow — a wrong workflow is worse than no workflow.
