---
name: linear
description: >
  Interact with Linear project management via the GraphQL API. Use when the user asks about
  Linear issues, tickets, tasks, sprints, cycles, projects, or team workload. Supports creating,
  updating, searching, filtering, archiving issues, managing cycles, and adding comments.
  Stdlib only — no external dependencies.
metadata: { "openclaw": { "primaryEnv": "LINEAR_API_KEY" } }
---

# Linear Skill

Interact with Linear's GraphQL API. Stdlib only (urllib, json). No pip dependencies.

## ⚠️ SAFETY: Write Operations Require Explicit User Request

**Read operations** (me, teams, states, labels, cycles, projects, issue, issues, search) — use freely.

**Write operations** (create-issue, update-issue, archive-issue, comment, create-cycle, batch-create, batch-update, create-project, create-project-update, update-project-update, delete-project-update, create-relation, attach-url, attach-slack, create-customer, update-customer) — **ONLY use when the user explicitly asks**. Never create, modify, or archive issues proactively.

**Important:** workspace-local policy may be stricter than this skill. If local instructions say ticket creation must go through another agent/form/workflow first, obey that gate before any Linear mutation.

**Workspace note:** asks like "review this and ensure all items have tickets", "make sure priorities are set", or "audit these notes and file the gaps" still count as write requests if fulfilling them would require Linear changes. Audit first if useful, but do not run Linear mutations until the local dogfooding/bypass check has passed.

## API Key

Reads from `LINEAR_API_KEY` env var (auto-injected via `skills.entries.linear.apiKey`).
Falls back to reading config directly.

**Option A: Personal API key** — Generate at https://linear.app/settings/api (simple, tied to a user).

**Option B: OAuth App** — For agent identities (so actions appear as the agent, not a human).
See `{baseDir}/references/oauth-setup.md` for the full flow. Linear OAuth tokens expire after ~24h — set up automated refresh.

## Base Command

```bash
python3 {baseDir}/scripts/linear.py [--pretty] <command> [args]
```

`--pretty` / `-p` — pretty-print JSON output. All commands output JSON.

## Read Commands

### me — Authenticated user info
```bash
python3 {baseDir}/scripts/linear.py me
```

### teams — List all teams
```bash
python3 {baseDir}/scripts/linear.py teams
```
Returns `id`, `name`, `key`. Use `id` (UUID) for `--team-id` in mutations.

### states — List workflow states
```bash
python3 {baseDir}/scripts/linear.py states [--team ENG]
```
Returns `id`, `name`, `type` (backlog/unstarted/started/completed/cancelled), `position`.
Use `id` (UUID) for `--state-id` in mutations.

### labels — List all labels
```bash
python3 {baseDir}/scripts/linear.py labels
```
Returns `id`, `name`, `color`. Use `id` (UUID) for `--label-ids` in mutations.

### cycles — List cycles/sprints
```bash
python3 {baseDir}/scripts/linear.py cycles [--team ENG] [--limit 10]
```

### users — List all users
```bash
python3 {baseDir}/scripts/linear.py users
```
Returns `id`, `name`, `email`, `displayName`, `active`, `admin`. Useful for looking up assignee UUIDs.

### projects — List projects
```bash
python3 {baseDir}/scripts/linear.py projects [--limit 25]
```

### issue — Get single issue details
```bash
python3 {baseDir}/scripts/linear.py issue ENG-123
```
Returns full detail: title, description, state, assignee, labels, comments, sub-issues, etc.

### issues — List/filter issues
```bash
python3 {baseDir}/scripts/linear.py issues [filters...]
```
Filters:
- `--team ENG` — by team key
- `--state "In Progress" "In Review"` — by state name(s)
- `--assignee "Nick"` — by assignee name (partial match)
- `--label "Bug" "P0"` — by label name(s)
- `--priority 2` — max priority (1=urgent, 2=high, 3=medium, 4=low)
- `--project "Auth"` — by project name (partial match)
- `--cycle "Sprint 5"` — by cycle name (partial match)
- `--limit 50` — max results (default 50)
- `--after <cursor>` — pagination cursor from `pageInfo.endCursor`

### batch-get — Fetch multiple issues by identifier
```bash
python3 {baseDir}/scripts/linear.py batch-get ENG-123 ENG-124 ENG-125
```
Fetches full issue details for multiple identifiers in a single batched query (using GraphQL aliases, 10 per round trip). Returns the same detail level as the single `issue` command. Issues not found are skipped with a warning to stderr.

### search — Full-text search issues
```bash
python3 {baseDir}/scripts/linear.py search "login bug"
```
Searches title and description (case-insensitive). Use `--limit` to control results.

## Write Commands

### create-issue — Create a new issue
```bash
python3 {baseDir}/scripts/linear.py create-issue \
  --team-id <TEAM_UUID> \
  --title "Issue title" \
  [--description "Markdown body"] \
  [--assignee-id <USER_UUID>] \
  [--state-id <STATE_UUID>] \
  [--label-ids <UUID> <UUID>] \
  [--priority 2] \
  [--project-id <UUID>] \
  [--cycle-id <UUID>] \
  [--estimate 3] \
  [--parent-id <UUID>]
```
Priority scale: 0=none, 1=urgent, 2=high, 3=medium, 4=low.

### update-issue — Update an existing issue
```bash
python3 {baseDir}/scripts/linear.py update-issue ENG-123 \
  [--title "New title"] \
  [--state-id <STATE_UUID>] \
  [--assignee-id <USER_UUID>] \
  [--priority 1] \
  ...
```
Accepts same optional fields as create-issue (except --team-id).

### archive-issue — Archive an issue
```bash
python3 {baseDir}/scripts/linear.py archive-issue ENG-123
```

### comment — Add a comment
```bash
python3 {baseDir}/scripts/linear.py comment \
  --issue-id <ISSUE_UUID> \
  --body "Comment in **markdown**"
```
Note: requires the issue UUID (from `issue` command's `id` field), not the identifier.

### create-relation — Create an issue relation (blocking, duplicate, related)
```bash
python3 {baseDir}/scripts/linear.py create-relation \
  --issue-id <SOURCE_UUID> \
  --related-issue-id <RELATED_UUID> \
  --type blocks|duplicate|related
```
Relation types:
- `blocks` — source blocks the related issue
- `duplicate` — marks as duplicate
- `related` — general relation

### create-project — Create a project
```bash
python3 {baseDir}/scripts/linear.py create-project \
  --name "Project Name" \
  --team-ids <TEAM_UUID> [<TEAM_UUID>...] \
  [--description "Description"] \
  [--lead-id <USER_UUID>] \
  [--start-date 2026-03-01] \
  [--target-date 2026-06-01]
```

### project-updates — List project updates
```bash
python3 {baseDir}/scripts/linear.py project-updates "Project Name" \
  [--limit 25] [--after <cursor>] [--order-by updatedAt] [--include-archived]
```
Lists status updates for a project. Accepts project name (partial match) or UUID.

### project-update — Get a single project update
```bash
python3 {baseDir}/scripts/linear.py project-update <UPDATE_UUID>
```

### create-project-update — Post a project update
```bash
python3 {baseDir}/scripts/linear.py create-project-update \
  --project "Project Name" \
  --body "## Week of Feb 24\n\nShipped feature X..." \
  [--health onTrack|atRisk|offTrack] \
  [--hide-diff]
```
Health status options: `onTrack`, `atRisk`, `offTrack`.

### update-project-update — Edit a project update
```bash
python3 {baseDir}/scripts/linear.py update-project-update <UPDATE_UUID> \
  [--body "Updated content"] \
  [--health atRisk] \
  [--hide-diff true|false]
```

### delete-project-update — Delete a project update
```bash
python3 {baseDir}/scripts/linear.py delete-project-update <UPDATE_UUID>
```

### attach-url — Attach a URL to an issue
```bash
python3 {baseDir}/scripts/linear.py attach-url \
  --issue-id <ISSUE_UUID> \
  --url "https://example.com" \
  --title "Display title" \
  [--subtitle "Subtitle text"] \
  [--icon-url "https://..."]
```
Attaches a generic URL as a linked resource in the issue sidebar. Use for PRs, docs, external links, etc. Title is required.

### attach-slack — Link a Slack message/thread to an issue (preferred for Slack)
```bash
python3 {baseDir}/scripts/linear.py attach-slack \
  --issue-id <ISSUE_UUID> \
  --url "https://example-org.slack.com/archives/C.../p..." \
  [--title "Discussion thread"] \
  [--sync]
```
Uses Linear's native `attachmentLinkSlack` mutation — shows a Slack-branded attachment in the sidebar. **This is the preferred way to link Slack threads to Linear issues** (not `attach-url`, not pasting in description).

- `--sync` enables bidirectional comment sync: Slack thread replies appear as Linear comments and vice versa. The Slack thread also gets updated when the issue is completed/cancelled.
- Without `--sync`, it's a one-way link (Slack URL appears in the issue sidebar, no comment sync).
- Requires the Linear ↔ Slack integration to be configured in your Linear workspace.

### batch-update — Update multiple issues at once (max 250)
```bash
python3 {baseDir}/scripts/linear.py batch-update ENG-123 ENG-124 ENG-125 \
  [--state-id <STATE_UUID>] \
  [--assignee-id <USER_UUID>] \
  [--priority 2] \
  [--label-ids <UUID> <UUID>] \
  [--add-label-ids <UUID>] \
  [--remove-label-ids <UUID>] \
  [--project-id <UUID>] \
  [--cycle-id <UUID>] \
  [--estimate 3] \
  [--due-date 2026-03-15] \
  [--title "New title"] \
  [--description "New description"]
```
Uses Linear's native `issueBatchUpdate` mutation — applies the **same** changes to all listed issues in a single API call. Accepts issue identifiers (ENG-123 format); resolves them to UUIDs automatically.

Extra label flags vs `update-issue`:
- `--label-ids` — replace all labels (same as single update)
- `--add-label-ids` — add labels without removing existing ones
- `--remove-label-ids` — remove specific labels without affecting others

### batch-create — Create multiple issues at once
```bash
python3 {baseDir}/scripts/linear.py batch-create issues.json
# or from stdin:
echo '[{"teamId":"<UUID>","title":"Issue 1"},{"teamId":"<UUID>","title":"Issue 2"}]' | \
  python3 {baseDir}/scripts/linear.py batch-create -
```
Uses Linear's native `issueBatchCreate` mutation. Input is a JSON array where each element uses the same fields as `create-issue` (camelCase keys: `teamId`, `title`, `description`, `assigneeId`, `stateId`, `labelIds`, `priority`, `projectId`, `cycleId`, `estimate`, `parentId`). Both `teamId` and `title` are required per issue.

### create-cycle — Create a cycle/sprint
```bash
python3 {baseDir}/scripts/linear.py create-cycle \
  --team-id <TEAM_UUID> \
  --starts "2026-03-01" \
  --ends "2026-03-14" \
  [--name "Sprint 7"]
```

## Customer Commands

### customers — List customers
```bash
python3 {baseDir}/scripts/linear.py customers [--name "Acme"] [--tier "Tier 1"] [--status "Active"] [--limit 50] [--after <cursor>] [--include-archived]
```
Returns `id`, `name`, `domains`, `revenue`, `size`, `owner`, `status`, `tier`, `url`, etc. Filters accept names or UUIDs.

### customer — Get a single customer
```bash
python3 {baseDir}/scripts/linear.py customer "Acme Corp"
python3 {baseDir}/scripts/linear.py customer <CUSTOMER_UUID>
```
Accepts a customer name (exact match, case-insensitive) or UUID.

### customer-requests — List customer requests
```bash
python3 {baseDir}/scripts/linear.py customer-requests [--customer "Acme Corp"] [--priority 1] [--issue-id <UUID>] [--limit 50] [--after <cursor>] [--include-archived]
```
Lists customer requests (needs). Filter by customer name/UUID, priority, or linked issue.

### customer-request — Get a single customer request
```bash
python3 {baseDir}/scripts/linear.py customer-request <REQUEST_UUID>
```

### customer-statuses — List customer statuses
```bash
python3 {baseDir}/scripts/linear.py customer-statuses [--include-archived]
```
Returns `id`, `name`, `displayName`, `color`, `position`. Use for resolving status names to UUIDs.

### customer-tiers — List customer tiers
```bash
python3 {baseDir}/scripts/linear.py customer-tiers [--include-archived]
```
Returns `id`, `name`, `displayName`, `color`, `position`. Use for resolving tier names to UUIDs.

### create-customer — Create a customer
```bash
python3 {baseDir}/scripts/linear.py create-customer \
  --name "Acme Corp" \
  [--domains acme.com acme.io] \
  [--external-ids crm-123] \
  [--owner "alice@example.com"] \
  [--status "Active"] \
  [--tier "Tier 1"] \
  [--slack-channel-id C0123456] \
  [--revenue 500000] \
  [--size 200]
```
Owner, status, and tier accept names or UUIDs — resolved automatically.

### update-customer — Update a customer
```bash
python3 {baseDir}/scripts/linear.py update-customer "Acme Corp" \
  [--name "New Name"] \
  [--domains newdomain.com] \
  [--owner "bob@example.com"] \
  [--status "Churned"] \
  [--tier "Tier 2"] \
  [--revenue 1000000]
```
First argument is the customer name or UUID. Pass empty string for `--owner`, `--status`, `--tier`, or `--slack-channel-id` to clear the field.

## Common Workflows

### Create an issue (full flow)
1. `teams` → get team UUID
2. `states --team ENG` → get desired state UUID
3. `labels` → get label UUIDs (optional)
4. `create-issue --team-id <UUID> --title "..." ...`

### Move an issue to a different state
1. `states --team ENG` → find target state UUID
2. `update-issue ENG-123 --state-id <STATE_UUID>`

### Triage: list open issues by priority
```bash
python3 {baseDir}/scripts/linear.py issues --team ENG --priority 2 --state "In Progress" "Todo"
```

## Notes

- All identifiers like `ENG-123` work for `issue`, `update-issue`, and `archive-issue`.
- Mutations (create/update) require UUIDs for team, state, label, assignee, etc. Use the read commands to look these up.
- Output is always JSON. Pipe through `jq` for shell scripting, or use `--pretty` for readability.
- Rate limit: 5,000 requests/hour with API key.
- Pagination: `issues` returns `pageInfo.hasNextPage` and `pageInfo.endCursor`. Pass `--after <cursor>` for next page.

## References

- `{baseDir}/references/oauth-setup.md` — Full OAuth flow for agent identities
- `{baseDir}/references/ids-template.md` — Template for saving org-specific IDs locally

After running discovery queries, save your team/state/project/user IDs to `references/ids.md` (gitignored) for quick access.

## Not Covered (use MCP or direct GraphQL for these)

- Roadmaps / Initiatives
- Webhook management
- Attachment uploads (file-based; URL attachments supported via `attach-url`)
- Document creation/editing
- Template management
- Team/label/state CRUD (admin ops)
