#!/usr/bin/env python3
"""
Notion API client — stdlib only (urllib, json).
Covers common operations via Notion's REST API.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = "https://api.notion.com/v1"
API_VERSION = "2022-06-28"


def load_token():
    """Read Notion integration token from OpenClaw config or env var."""
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    try:
        with open(config_path) as f:
            config = json.load(f)
        return config["skills"]["entries"]["notion"]["apiKey"]
    except (FileNotFoundError, KeyError, TypeError):
        pass
    # Check both env var names (NOTION_API_KEY from primaryEnv, NOTION_TOKEN as fallback)
    token = os.environ.get("NOTION_API_KEY") or os.environ.get("NOTION_TOKEN")
    if token:
        return token
    # Fallback: local token file (do not print contents)
    token_path = Path.home() / ".config" / "notion" / "api_key"
    try:
        token = token_path.read_text().strip()
        if token:
            return token
    except FileNotFoundError:
        pass

    print(
        "Error: No Notion token. Set skills.entries.notion.apiKey in openclaw.json "
        "or NOTION_API_KEY env var.",
        file=sys.stderr,
    )
    sys.exit(1)


def api(method, path, body=None, _retries=3):
    """Make an API request to Notion with retry on 429."""
    token = load_token()
    url = f"{API_BASE}{path}"
    payload = json.dumps(body).encode() if body else None
    for attempt in range(_retries):
        req = urllib.request.Request(
            url,
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": API_VERSION,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < _retries - 1:
                wait = int(e.headers.get("Retry-After", 2 ** attempt))
                print(f"Rate limited, retrying in {wait}s...", file=sys.stderr)
                import time
                time.sleep(wait)
                continue
            body_text = e.read().decode()
            print(f"HTTP {e.code}: {body_text}", file=sys.stderr)
            sys.exit(1)


def out(data, pretty=False):
    """Print JSON output."""
    print(json.dumps(data, indent=2) if pretty else json.dumps(data))


# ---------------------------------------------------------------------------
# Read Commands
# ---------------------------------------------------------------------------


def cmd_search(args):
    """Search the workspace for pages and databases."""
    body = {}
    if args.query:
        body["query"] = args.query
    if args.type:
        body["filter"] = {"property": "object", "value": args.type}
    if args.limit:
        body["page_size"] = args.limit
    if args.cursor:
        body["start_cursor"] = args.cursor
    result = api("POST", "/search", body)
    out(result, args.pretty)


def cmd_databases(args):
    """List databases via search (filtered to databases)."""
    body = {"filter": {"property": "object", "value": "database"}}
    if args.query:
        body["query"] = args.query
    if args.limit:
        body["page_size"] = args.limit
    result = api("POST", "/search", body)
    # Simplify output: extract key fields
    items = []
    for db in result.get("results", []):
        title_parts = db.get("title", [])
        title = "".join(t.get("plain_text", "") for t in title_parts)
        props = {k: v.get("type", "?") for k, v in db.get("properties", {}).items()}
        items.append({
            "id": db["id"],
            "title": title,
            "url": db.get("url", ""),
            "properties": props,
        })
    out(items, args.pretty)


def cmd_database(args):
    """Get a database schema by ID."""
    result = api("GET", f"/databases/{args.database_id}")
    out(result, args.pretty)


def cmd_query(args):
    """Query a database with optional filters."""
    body = {}
    if args.filter:
        try:
            body["filter"] = json.loads(args.filter)
        except json.JSONDecodeError:
            print("Error: --filter must be valid JSON.", file=sys.stderr)
            sys.exit(1)
    if args.sort:
        try:
            body["sorts"] = json.loads(args.sort)
        except json.JSONDecodeError:
            print("Error: --sort must be valid JSON.", file=sys.stderr)
            sys.exit(1)
    if args.limit:
        body["page_size"] = args.limit
    if args.cursor:
        body["start_cursor"] = args.cursor
    result = api("POST", f"/databases/{args.database_id}/query", body)
    out(result, args.pretty)


def cmd_page(args):
    """Get a page by ID."""
    result = api("GET", f"/pages/{args.page_id}")
    out(result, args.pretty)


def cmd_blocks(args):
    """Get block children (page content)."""
    params = []
    if args.limit:
        params.append(f"page_size={args.limit}")
    if args.cursor:
        params.append(f"start_cursor={args.cursor}")
    qs = f"?{'&'.join(params)}" if params else ""
    result = api("GET", f"/blocks/{args.block_id}/children{qs}")
    out(result, args.pretty)


def cmd_users(args):
    """List workspace users."""
    result = api("GET", "/users")
    items = []
    for u in result.get("results", []):
        items.append({
            "id": u["id"],
            "type": u.get("type", ""),
            "name": u.get("name", ""),
            "email": u.get("person", {}).get("email", ""),
        })
    out(items, args.pretty)


def cmd_comments(args):
    """List comments on a page or block."""
    params = [f"block_id={args.block_id}"]
    if args.limit:
        params.append(f"page_size={args.limit}")
    if args.cursor:
        params.append(f"start_cursor={args.cursor}")
    result = api("GET", f"/comments?{'&'.join(params)}")
    out(result, args.pretty)


# ---------------------------------------------------------------------------
# Write Commands — USE ONLY WHEN EXPLICITLY REQUESTED BY USER
# ---------------------------------------------------------------------------


def cmd_create_page(args):
    """Create a new page under a database or page parent."""
    if args.database_id:
        body = {"parent": {"database_id": args.database_id}}
    elif args.page_id:
        body = {"parent": {"page_id": args.page_id}}
    else:
        print("Error: provide --database-id or --page-id.", file=sys.stderr)
        sys.exit(1)

    # Parse properties JSON
    if args.properties:
        try:
            body["properties"] = json.loads(args.properties)
        except json.JSONDecodeError:
            print("Error: --properties must be valid JSON.", file=sys.stderr)
            sys.exit(1)
    else:
        body["properties"] = {}

    # Parse optional children blocks
    if args.children:
        try:
            body["children"] = json.loads(args.children)
        except json.JSONDecodeError:
            print("Error: --children must be valid JSON.", file=sys.stderr)
            sys.exit(1)

    result = api("POST", "/pages", body)
    out(result, args.pretty)


def cmd_update_page(args):
    """Update a page's properties."""
    body = {}
    if args.properties:
        try:
            body["properties"] = json.loads(args.properties)
        except json.JSONDecodeError:
            print("Error: --properties must be valid JSON.", file=sys.stderr)
            sys.exit(1)
    if args.archive:
        body["archived"] = True

    if not body:
        print("Error: provide --properties or --archive.", file=sys.stderr)
        sys.exit(1)

    result = api("PATCH", f"/pages/{args.page_id}", body)
    out(result, args.pretty)


def cmd_archive_page(args):
    """Archive (soft-delete) a page."""
    result = api("PATCH", f"/pages/{args.page_id}", {"archived": True})
    out(result, args.pretty)


def cmd_append_blocks(args):
    """Append blocks to a page or block."""
    try:
        children = json.loads(args.children)
    except json.JSONDecodeError:
        print("Error: --children must be valid JSON.", file=sys.stderr)
        sys.exit(1)

    result = api("PATCH", f"/blocks/{args.block_id}/children", {"children": children})
    out(result, args.pretty)


def cmd_add_comment(args):
    """Add a comment to a page."""
    body = {
        "parent": {"page_id": args.page_id},
        "rich_text": [{"type": "text", "text": {"content": args.body}}],
    }
    result = api("POST", "/comments", body)
    out(result, args.pretty)


def cmd_create_database(args):
    """Create a new database under a page parent."""
    body = {
        "parent": {"page_id": args.page_id},
        "title": [{"type": "text", "text": {"content": args.title}}],
    }
    if args.inline:
        body["is_inline"] = True
    try:
        body["properties"] = json.loads(args.properties)
    except json.JSONDecodeError:
        print("Error: --properties must be valid JSON.", file=sys.stderr)
        sys.exit(1)
    result = api("POST", "/databases", body)
    out(result, args.pretty)


def cmd_update_block(args):
    """Update an existing block's content."""
    try:
        block_data = json.loads(args.data)
    except json.JSONDecodeError:
        print("Error: --data must be valid JSON.", file=sys.stderr)
        sys.exit(1)
    result = api("PATCH", f"/blocks/{args.block_id}", block_data)
    out(result, args.pretty)


def cmd_delete_block(args):
    """Archive (soft-delete) a block."""
    result = api("DELETE", f"/blocks/{args.block_id}")
    out(result, args.pretty)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Notion API client (stdlib, no deps)"
    )
    parser.add_argument(
        "--pretty", "-p", action="store_true", help="Pretty-print JSON"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- Read commands --
    p = sub.add_parser("search", help="Search workspace")
    p.add_argument("query", nargs="?", help="Search text")
    p.add_argument("--type", choices=["page", "database"], help="Filter by type")
    p.add_argument("--limit", "-l", type=int, default=20)
    p.add_argument("--cursor", help="Pagination cursor")

    p = sub.add_parser("databases", help="List databases")
    p.add_argument("--query", "-q", help="Filter by name")
    p.add_argument("--limit", "-l", type=int, default=20)

    p = sub.add_parser("database", help="Get database schema")
    p.add_argument("database_id", help="Database UUID")

    p = sub.add_parser("query", help="Query a database")
    p.add_argument("database_id", help="Database UUID")
    p.add_argument("--filter", "-f", help="Filter JSON (Notion filter object)")
    p.add_argument("--sort", "-s", help="Sort JSON (array of sort objects)")
    p.add_argument("--limit", "-l", type=int, default=50)
    p.add_argument("--cursor", help="Pagination cursor")

    p = sub.add_parser("page", help="Get page details")
    p.add_argument("page_id", help="Page UUID")

    p = sub.add_parser("blocks", help="Get block children (page content)")
    p.add_argument("block_id", help="Block or page UUID")
    p.add_argument("--limit", "-l", type=int)
    p.add_argument("--cursor", help="Pagination cursor")

    p = sub.add_parser("users", help="List workspace users")

    p = sub.add_parser("comments", help="List comments on a page/block")
    p.add_argument("block_id", help="Page or block UUID")
    p.add_argument("--limit", "-l", type=int)
    p.add_argument("--cursor", help="Pagination cursor")

    # -- Write commands (require explicit user request) --
    p = sub.add_parser("create-page", help="[WRITE] Create page in database or under page")
    p.add_argument("--database-id", help="Database UUID (parent)")
    p.add_argument("--page-id", help="Page UUID (parent)")
    p.add_argument("--properties", help="Properties JSON")
    p.add_argument("--children", help="Children blocks JSON (optional)")

    p = sub.add_parser("update-page", help="[WRITE] Update page properties")
    p.add_argument("page_id", help="Page UUID")
    p.add_argument("--properties", help="Properties JSON")
    p.add_argument("--archive", action="store_true", help="Archive the page")

    p = sub.add_parser("archive-page", help="[WRITE] Archive a page")
    p.add_argument("page_id", help="Page UUID")

    p = sub.add_parser("append-blocks", help="[WRITE] Append blocks to page")
    p.add_argument("block_id", help="Page or block UUID")
    p.add_argument("--children", required=True, help="Children blocks JSON")

    p = sub.add_parser("add-comment", help="[WRITE] Add comment to page")
    p.add_argument("--page-id", required=True, help="Page UUID")
    p.add_argument("--body", "-b", required=True, help="Comment text")

    p = sub.add_parser("create-database", help="[WRITE] Create database under page")
    p.add_argument("--page-id", required=True, help="Parent page UUID")
    p.add_argument("--title", required=True, help="Database title")
    p.add_argument("--properties", required=True, help="Properties schema JSON")
    p.add_argument("--inline", action="store_true", help="Create as inline database")

    p = sub.add_parser("update-block", help="[WRITE] Update a block's content")
    p.add_argument("block_id", help="Block UUID")
    p.add_argument("--data", "-d", required=True, help="Block data JSON (e.g. {\"paragraph\": {\"rich_text\": [...]}})")

    p = sub.add_parser("delete-block", help="[WRITE] Delete (archive) a block")
    p.add_argument("block_id", help="Block UUID")

    args = parser.parse_args()

    cmd_map = {
        "search": cmd_search,
        "databases": cmd_databases,
        "database": cmd_database,
        "query": cmd_query,
        "page": cmd_page,
        "blocks": cmd_blocks,
        "users": cmd_users,
        "comments": cmd_comments,
        "create-page": cmd_create_page,
        "update-page": cmd_update_page,
        "archive-page": cmd_archive_page,
        "append-blocks": cmd_append_blocks,
        "add-comment": cmd_add_comment,
        "create-database": cmd_create_database,
        "update-block": cmd_update_block,
        "delete-block": cmd_delete_block,
    }
    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
