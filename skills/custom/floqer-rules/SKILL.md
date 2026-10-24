---
name: floqer-rules
description: Use when planning, scoping, or building ANY Floqer GTM workflow — choosing actions or data sources, configuring or PATCHing an action, wiring {{references}}, pushing rows, or running a chain — AND when debugging Floqer (an action errors, a PATCH is rejected or silently ignored, references resolve empty/null, a filter or run_if won't fire, or output looks wrong). Establishes the mandatory read-the-docs gates and lean-build discipline before you touch the Floqer API.
---

# Floqer — Rules of Engagement

Floqer's behavior is **not** inferable from intuition. Input shapes, operator dialects, schema discovery, and run semantics are full of traps that look like they work and then silently fail. **The docs are the source of truth. You do not plan, configure, PATCH, or run anything you have not just read the doc for.** Every rule below exists because the mistake it prevents has already been made.

Docs live in `floqer-context/content/docs/` — the canonical tree, and what FLO and external MCP clients read (`read_doc`). `https://floqer.com/docs/` serves an older subset and does not carry the ackDB library at all; prefer the repo or `read_doc`. **Read the actual file each time — never rely on memory of a prior read; the docs change.**

## Build lean — the shortest chain that works
There is a strong pull to keep *adding* actions and end up with a sprawling flow. Resist it. Every action is a cost, a failure point, and one more thing the next person has to understand. Before adding one, ask whether an existing action — or a single `format_data_using_js_expression` — already covers it. Consolidate steps. **Delete actions that became redundant — a flow that got shorter is almost always better.** Streamline; don't bolt on.

**Name every action you add.** A sheet full of `format_data_using_js_expression_01xz` / `llm_models_01cg` is unreadable to the human who owns it. Give each action a short, meaningful display name describing what it produces (`Months in current role`, `Director title? (is_director)`, `Qualifies: director + <7mo`) — pass `name` at create time (`POST .../actions/add`) or PATCH `.../actions/{id}/name` after. The latter does NOT invalidate the row cache, so relabel freely any time. Do this as you build, not as a cleanup pass.

## Design rules — pick the right primitive
- **Web agent researches, LLM writes — always chain.** `llm_web_agents` retrieve facts from the web; `llm_models` write, classify, and transform. Don't make a web agent write outreach, or an LLM "research" (it hallucinates). The pattern is a chain: web agent gathers → LLM writes from what it gathered.
- **Prompt for content, not structure.** Tell an agent what each field should *contain*; put the output shape in `output_format`, not in the prompt prose. Structural prose in the prompt makes agents fixate on format and drop content on edge-case rows.
- **Default `llm_web_agents` to `floqer-nova`** — the capable go-to across light and heavy research; for a heavy non-Floqer model use Parallel Core / GPT-5.2. (Model availability shifts — confirm against the action's options if unsure.)

## The read-gates — READ FIRST, BUILD SECOND
Each gate ends in what to read. If you skipped one, you'll hit its "skipped-me" tell.

**G0 — KNOW THE CUSTOMER.** Before planning, call `get_user_knowledge` (REST: `GET /api/v1/user/knowledge`) and branch on `exists`:
- **Exists** → treat its ICP gate, personas, regions, and proof points as **authoritative parameters** — wire them as hard values (filters / run_if / copy) and **ask before deviating**. Never act on an unstated assumption about who the customer targets.
- **`exists: false` / empty** → this org **has not been onboarded**. Say so, gather the basics from the user (what they sell and to whom, ICP, regions, key goals), and write a focused brief with `set_user_knowledge` *before* building — do NOT plan against an empty file or fabricate customer context.

**G1 — START FROM A USE CASE, NOT A BLANK CHAIN.** Before designing any workflow, read `use-case-catalog.txt`, then open the matched `use-case-detail/<slug>.txt` **in full**. *Skipped-me tell: you're inventing an action order from scratch.*

**G2 — READ THE DETAIL BEFORE YOU TOUCH AN ACTION OR SOURCE.** For every action you add or configure, Read `action-detail/<id>.txt` — especially its HOW TO CONFIGURE and KEY NOTES sections — **before** writing the PATCH body. For every data source, Read `source-catalog.txt` + `source-detail/<id>.txt`. The KEY NOTES / lifecycle sections are where the silent failures are documented. *Skipped-me tell: you guessed an input field name or value.*

**G3 — KNOW THE ENDPOINT SHAPES & MODEL.** For any API call you're unsure of, read `concepts.txt` — it carries both the endpoint shapes (`rows/list` with `status_filters` / `row_ids` / `run_next_action`, dropdown options, sources in §10) and the mental model (action_id vs action_instance_id, `{{references}}`, scalar vs nested data types). Don't pattern-match an endpoint from another one.

**G4 — GET BEFORE YOU PATCH.** Always `GET` the action and **mirror its persisted shape** before PATCHing. run_if vs filter shapes and operator dialects diverge and are silently accepted when wrong. *Skipped-me tell: a PATCH returns 200 but nothing changes, or a 400 "must have required property."*

**G5 — TEST AT THE CELL, NOT THE ROW — and discover dynamic schema by stepping cells.** The cheap, fast way to test anything is to run a single action's **cell**: Run Action with **`run_next_action: false`**. Reach for it constantly while building — don't run a whole row to check one action. This is essential for dynamic-output actions (`raw_to_structured_array`, `llm_web_agents`, lookups), which only reveal their real columns after running on real data: run the upstream producer cell, then the dynamic-output cell itself (each with **no cascade**), then call Get Action Outputs (`GET .../actions/{action_instance_id}/outputs`) to read the columns before wiring downstream `{{refs}}`. Resolve dropdowns via Get Action Field Options (`POST .../actions/{action_instance_id}/options/{field_name}`) first. **Never cascade a row to discover schema** (`run_next_action: true` / Run Rows) — it fires still-half-configured downstream actions like `push_data_to_sheet` and flushes junk rows into the destination sheet. *Skipped-me tell: a downstream ref resolves empty / `unresolved_reference`, or a destination sheet fills with garbage rows.*

**G6 — PROVE ON 1–3 ROWS, THEN SCALE WITH FILTERS.** Run on 1–3 rows and read **per-cell** status before Run All — paid per-row actions burn credits, and a wrong assumption ×100 rows is real money. To run a **large dataset** or **re-run failed actions, scope the run — never blanket Run All.** `rows/list` exposes the **status** of every action's cell (not its output content): use `status_filters` to pull just the rows whose target cell is `failed`/`error` (or any status), collect those `row_ids`, and Run Action on only those. To target by an output **value** (not filterable directly), tag it first with a `filter` action or a JS `YES`/`NO` formatter, then query that gate's status. *(See `concepts.txt` → rows/list.)*

## Verify-then-apply
When something contradicts what you expected, **re-read the doc and `GET` the live action before acting**. Don't act on an uninformed assumption — *yours or the user's*. A suggestion that isn't grounded in the doc or the live state gets verified before it's built. Verifying is cheaper than undoing.

## Authoring API calls
When you PATCH a JS formatter — or any body containing backslashes, regex, or quotes — build the JSON with Python `json.dumps` (or write it to a file), **never a shell heredoc**. Heredocs mangle regex backslashes and escape sequences and silently corrupt the stored JS.

## When you hit a NEW gotcha (not in the docs)
Write it to project memory as one fact with a `Verify:` probe and a `PROMOTE-TO: <doc file> WHEN: <verified>` line — **not** into this skill, which stays facts-free. Once you've confirmed it against the live API, promote it into the owning `action-detail/<id>.txt` §4 KEY NOTES with a `Verified <date>` marker, and delete the memory note. A stale fact buried in a skill is worse than no fact.
