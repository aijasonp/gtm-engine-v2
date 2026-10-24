---
name: notion
description: >
  Full Notion workspace integration: CRUD operations via Python CLI (stdlib,
  no deps), markdown↔Notion block conversion via Node.js scripts, and
  one-command page publishing with auto-batching. Use when asked to search,
  read, create, update, or manage Notion pages, databases, blocks, comments,
  or when converting between markdown and Notion format.
metadata:
  version: 2.0.0
  openclaw:
    emoji: "📝"
    primaryEnv: NOTION_API_KEY
---

# Notion Skill

Two toolchains, one skill: a Python CLI for full Notion API CRUD, and Node.js
scripts for markdown↔Notion conversion. Use whichever fits the task.

## Setup

1. Get a token: [notion.so/my-integrations](https://notion.so/my-integrations) → New integration
2. Store it: `mkdir -p ~/.config/notion && echo "ntn_..." > ~/.config/notion/api_key`
3. Share target pages/databases with your integration in Notion (click "..." → "Connect to")
4. For Node.js scripts: `cd <skill-dir>/scripts && npm install`

The Python CLI also reads `NOTION_API_KEY` env var or `skills.entries.notion.apiKey` from OpenClaw config.

**Important:** The integration only sees pages/databases you explicitly share with it.

## ⚠️ SAFETY: Write Operations

**Read operations** (search, query, list, get, export) — use freely.

**Write operations** (create, update, archive, delete, append, publish) — **ONLY when the user explicitly asks**. All write CLI commands are marked `[WRITE]`.

---

## When to Use Which

**Default to markdown scripts for content.** Writing markdown is simpler and less
error-prone than hand-crafting Notion block JSON.

| Task | Use | Tool |
|------|-----|------|
| **Write** content to a new page | **Node.js** | `publish-to-notion.mjs` — write markdown, get auto-batching |
| **Write** content to existing page | **Node.js** | `md-to-notion.mjs` → feed JSON into `append-blocks` |
| **Read** a page's content | **Node.js** | `notion-to-md.mjs` — always prefer this over raw `blocks` |
| Search / query databases | Python CLI | `search`, `query`, `databases` |
| Get page properties or metadata | Python CLI | `page` |
| Get raw block IDs (for editing/deleting) | Python CLI | `blocks` — only when you need IDs for `update-block`/`delete-block` |
| Update page properties (status, dates, etc.) | Python CLI | `update-page` |
| Create/manage databases | Python CLI | `create-database`, `database` |
| Edit or delete individual blocks | Python CLI | `update-block`, `delete-block` |
| Archive pages | Python CLI | `archive-page` |
| Comments | Python CLI | `comments`, `add-comment` |
| List users | Python CLI | `users` |

**Rule of thumb:** Reading or writing content → always use the markdown scripts.
Querying, updating properties, or managing structure → Python CLI.

---

## Python CLI — Full Notion API

```bash
python3 <skill-dir>/scripts/notion.py [--pretty] <command> [args]
```

Stdlib only (urllib, json). No pip install needed. All commands output JSON.

### Read Commands

**search** — Search the workspace
```bash
python3 <skill-dir>/scripts/notion.py search "project plan"
python3 <skill-dir>/scripts/notion.py search --type database
python3 <skill-dir>/scripts/notion.py search "meeting notes" --type page --limit 10
```

**databases** — List accessible databases
```bash
python3 <skill-dir>/scripts/notion.py databases
python3 <skill-dir>/scripts/notion.py databases --query "Tasks"
```

**database** — Get database schema
```bash
python3 <skill-dir>/scripts/notion.py database <DATABASE_UUID>
```
Use this to see property names/types before creating pages.

**query** — Query a database with filters and sorts
```bash
python3 <skill-dir>/scripts/notion.py query <DATABASE_UUID>
python3 <skill-dir>/scripts/notion.py query <DB_UUID> \
  --filter '{"property": "Status", "select": {"equals": "To Do"}}' \
  --sort '[{"property": "Due Date", "direction": "ascending"}]'
python3 <skill-dir>/scripts/notion.py query <DB_UUID> --cursor <next_cursor>
```

**page** — Get page details (properties, metadata)
```bash
python3 <skill-dir>/scripts/notion.py page <PAGE_UUID>
```

**blocks** — Get page content (block children)
```bash
python3 <skill-dir>/scripts/notion.py blocks <PAGE_OR_BLOCK_UUID>
python3 <skill-dir>/scripts/notion.py blocks <UUID> --limit 50 --cursor <next_cursor>
```

**users** — List workspace users
```bash
python3 <skill-dir>/scripts/notion.py users
```

**comments** — List comments on a page/block
```bash
python3 <skill-dir>/scripts/notion.py comments <PAGE_UUID>
```

### Write Commands `[WRITE]`

**create-page** — Create page in database or under a page
```bash
# Under a database (structured)
python3 <skill-dir>/scripts/notion.py create-page \
  --database-id <DB_UUID> \
  --properties '{"Name": {"title": [{"text": {"content": "New item"}}]}}' \
  --children '[{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "Hello"}}]}}]'

# Under a page (freeform)
python3 <skill-dir>/scripts/notion.py create-page \
  --page-id <PAGE_UUID> \
  --properties '{"title": [{"text": {"content": "Sub-page"}}]}'
```
**Tip:** Run `database <ID>` first to see schema, then build matching properties.

**update-page** — Update page properties
```bash
python3 <skill-dir>/scripts/notion.py update-page <PAGE_UUID> \
  --properties '{"Status": {"select": {"name": "Done"}}}'
```

**archive-page** — Archive (soft-delete) a page
```bash
python3 <skill-dir>/scripts/notion.py archive-page <PAGE_UUID>
```

**append-blocks** — Append content blocks to a page/block
```bash
python3 <skill-dir>/scripts/notion.py append-blocks <PAGE_UUID> \
  --children '[{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "Appended"}}]}}]'
```

**add-comment** — Comment on a page
```bash
python3 <skill-dir>/scripts/notion.py add-comment --page-id <PAGE_UUID> --body "Looks good!"
```

**create-database** — Create a database under a page
```bash
python3 <skill-dir>/scripts/notion.py create-database \
  --page-id <PAGE_UUID> --title "Tasks" \
  --properties '{"Name": {"title": {}}, "Status": {"select": {"options": [{"name": "Todo"}, {"name": "Done"}]}}, "Due": {"date": {}}}' \
  --inline
```

**update-block** — Update an existing block's content
```bash
python3 <skill-dir>/scripts/notion.py update-block <BLOCK_UUID> \
  --data '{"paragraph": {"rich_text": [{"type": "text", "text": {"content": "Updated text"}}]}}'
```

**delete-block** — Delete (archive) a block
```bash
python3 <skill-dir>/scripts/notion.py delete-block <BLOCK_UUID>
```

---

## Node.js Scripts — Markdown ↔ Notion

Requires `npm install` in `<skill-dir>/scripts/`. Uses `@tryfabric/martian`, `notion-to-md`, `@notionhq/client`.

### Export: Notion Page → Markdown
```bash
node <skill-dir>/scripts/notion-to-md.mjs <page-id>
node <skill-dir>/scripts/notion-to-md.mjs <page-id> --output report.md
```
Handles nested blocks, tables, code blocks, links, formatting.

### Convert: Markdown → Notion Block JSON
```bash
node <skill-dir>/scripts/md-to-notion.mjs <markdown-file>
```
Outputs JSON array of Notion block objects to stdout. Pipe to a file or use in scripts.

### Publish: Markdown → New Notion Page
```bash
node <skill-dir>/scripts/publish-to-notion.mjs <parent-page-id> "Page Title" <markdown-file>
```
Creates a page under the parent, auto-batches blocks in groups of 100 (Notion API limit), with rate limiting between batches.

---

## Common Workflows

### Find and read a database
1. `databases` → find by name, get UUID
2. `database <UUID>` → see schema (property names and types)
3. `query <UUID>` → list entries with optional filters

### Read a page's content
1. `page <UUID>` → get properties (title, status, dates)
2. `blocks <UUID>` → get the actual content blocks

### Export a page to markdown
```bash
node <skill-dir>/scripts/notion-to-md.mjs <PAGE_UUID> --output page.md
```

### Publish markdown report to Notion
```bash
node <skill-dir>/scripts/publish-to-notion.mjs <PARENT_PAGE_UUID> "Weekly Report" report.md
```

### Create a task (in a database)
1. `databases` → find task database UUID
2. `database <UUID>` → check schema for required properties
3. `create-page --database-id <UUID> --properties '{...}'`

---

## Reference

### Block Types (for --children / --data JSON)

| Type | Key | Content Field |
|------|-----|---------------|
| Paragraph | `paragraph` | `rich_text` |
| Heading 1 | `heading_1` | `rich_text` |
| Heading 2 | `heading_2` | `rich_text` |
| Heading 3 | `heading_3` | `rich_text` |
| Bullet list | `bulleted_list_item` | `rich_text` |
| Numbered list | `numbered_list_item` | `rich_text` |
| To-do | `to_do` | `rich_text` + `checked` |
| Toggle | `toggle` | `rich_text` |
| Quote | `quote` | `rich_text` |
| Callout | `callout` | `rich_text` + `icon` |
| Code | `code` | `rich_text` + `language` |
| Divider | `divider` | (none) |
| Table | `table` | `table_width` + children `table_row` blocks |

All `rich_text` fields are arrays: `[{"type": "text", "text": {"content": "..."}}]`

### Property Types (for --properties JSON)

- **Title:** `{"title": [{"text": {"content": "..."}}]}`
- **Rich text:** `{"rich_text": [{"text": {"content": "..."}}]}`
- **Select:** `{"select": {"name": "Option"}}`
- **Multi-select:** `{"multi_select": [{"name": "A"}, {"name": "B"}]}`
- **Date:** `{"date": {"start": "2024-01-15", "end": "2024-01-16"}}`
- **Checkbox:** `{"checkbox": true}`
- **Number:** `{"number": 42}`
- **URL:** `{"url": "https://..."}`
- **Email:** `{"email": "a@b.com"}`
- **Relation:** `{"relation": [{"id": "page_id"}]}`

### Markdown ↔ Notion Mapping

| Markdown | Notion Block |
|----------|-------------|
| `# H1` | `heading_1` |
| `## H2` | `heading_2` |
| `### H3` | `heading_3` |
| `- item` | `bulleted_list_item` |
| `1. item` | `numbered_list_item` |
| `> quote` | `quote` |
| `` `code` `` | inline code annotation |
| ` ```lang ``` ` | `code` block |
| `**bold**` | bold annotation |
| `*italic*` | italic annotation |
| `~~strike~~` | strikethrough annotation |
| `[text](url)` | link annotation |
| `\| table \|` | `table` + `table_row` blocks |
| `---` | `divider` |

## Notes

- UUIDs: with or without dashes (Notion accepts both)
- Rate limit: ~3 req/sec. Python CLI retries on 429 with exponential backoff.
- Pagination: check `has_more` / `next_cursor` in response, pass `--cursor` for next page.
- Block limit: 100 blocks per API call. `publish-to-notion.mjs` handles batching automatically.
- The markdown converter (`@tryfabric/martian`) handles most common formatting; complex nested structures may need manual block JSON.
