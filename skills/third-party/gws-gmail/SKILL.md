---
name: gws-gmail
version: 1.0.0
description: "Gmail: Send, read, and manage email."
metadata:
  openclaw:
    category: "productivity"
    requires:
      bins: ["gws"]
    cliHelp: "gws gmail --help"
---

# gmail (v1)

> **PREREQUISITE:** Read `../gws-shared/SKILL.md` for auth, global flags, and security rules. If missing, run `gws generate-skills` to create it.

```bash
gws gmail <resource> <method> [flags]
```

## Helper Commands

### +send — Send an email

```bash
gws gmail +send --to <EMAIL> --subject <SUBJECT> --body <TEXT>
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--to` | ✓ | — | Recipient email address |
| `--subject` | ✓ | — | Email subject |
| `--body` | ✓ | — | Email body (plain text) |

```bash
gws gmail +send --to alice@example.com --subject 'Hello' --body 'Hi Alice!'
```

> **CAUTION:** Write command — confirm with user before executing.

### +triage — Show unread inbox summary (sender, subject, date)

```bash
gws gmail +triage
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--max` | — | 20 | Maximum messages to show |
| `--query` | — | — | Gmail search query (default: is:unread) |
| `--labels` | — | — | Include label names in output |

```bash
gws gmail +triage
gws gmail +triage --max 5 --query 'from:boss'
gws gmail +triage --format json | jq '.[].subject'
```

## API Resources

### users

  - `getProfile` — Gets the current user's Gmail profile.
  - `stop` — Stop receiving push notifications for the given user mailbox.
  - `watch` — Set up or update a push notification watch on the given user mailbox.
  - `drafts` — Operations on the 'drafts' resource
  - `history` — Operations on the 'history' resource
  - `labels` — Operations on the 'labels' resource
  - `messages` — Operations on the 'messages' resource
  - `settings` — Operations on the 'settings' resource
  - `threads` — Operations on the 'threads' resource

## Discovering Commands

Before calling any API method, inspect it:

```bash
# Browse resources and methods
gws gmail --help

# Inspect a method's required params, types, and defaults
gws schema gmail.<resource>.<method>
```

Use `gws schema` output to build your `--params` and `--json` flags.

