"""Collect the GTM agent outputs from the prior calendar month for evaluation.

Data sources:
1. MEDDPICC call summaries written to HubSpot (notes API)
2. Pre-call briefs (scripts/briefs/ + account-knowledge/)
3. Slack replies (OpenClaw session logs, message tool)
4. Structured JSON writes (HubSpot/Linear via exec in session logs)
"""
from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

WORKSPACE = Path(os.path.expanduser("~/.openclaw/workspace"))
SESSIONS_DIR = Path(os.path.expanduser("~/.openclaw/agents/main/sessions"))
BRIEFS_DIR = WORKSPACE / "scripts" / "briefs"
ACCOUNT_KNOWLEDGE_DIR = WORKSPACE / "account-knowledge"


def _load_env() -> dict:
    env = {}
    path = Path(os.path.expanduser("~/.openclaw/.env"))
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return env


@dataclass
class Sample:
    category: str
    output: str
    context: str = ""          # source material the output should be grounded in
    expected: str = ""         # expected/ground-truth (for task completion)
    source_id: str = ""        # link/ID for human review
    timestamp: str = ""
    meta: dict = field(default_factory=dict)


def _month_bounds(month: str) -> tuple[str, str]:
    """Return (start_iso, end_iso) for a YYYY-MM month."""
    y, m = int(month[:4]), int(month[5:7])
    start = datetime(y, m, 1, tzinfo=timezone.utc)
    if m == 12:
        end = datetime(y + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(y, m + 1, 1, tzinfo=timezone.utc)
    return start.isoformat(), end.isoformat()


# ---------------------------------------------------------------------------
# 1. HubSpot MEDDPICC call summaries
# ---------------------------------------------------------------------------
def collect_hubspot_notes(month: str, limit: int = 50) -> list[Sample]:
    env = _load_env()
    token = env.get("HUBSPOT_TOKEN")
    if not token:
        print("  [hubspot] no HUBSPOT_TOKEN, skipping")
        return []
    start_iso, end_iso = _month_bounds(month)
    samples: list[Sample] = []
    after = 0
    seen = 0
    while seen < limit:
        url = "https://api.hubapi.com/crm/v3/objects/notes/search"
        body = {
            "limit": 100,
            "after": after,
            "properties": ["hs_note_body", "hs_timestamp", "hs_created_by"],
            "filterGroups": [
                {
                    "filters": [
                        {"propertyName": "hs_timestamp", "operator": "GTE", "value": start_iso},
                        {"propertyName": "hs_timestamp", "operator": "LT", "value": end_iso},
                    ]
                }
            ],
        }
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        if r.status_code != 200:
            print(f"  [hubspot] search failed {r.status_code}: {r.text[:200]}")
            break
        data = r.json()
        results = data.get("results", [])
        for rec in results:
            props = rec.get("properties", {})
            body = props.get("hs_note_body") or ""
            # Only MEDDPICC / post-call brief notes
            if not re.search(r"MEDDPICC|Post-Call Brief|ICP Post-Call", body, re.IGNORECASE):
                continue
            # Strip HTML
            text = re.sub(r"<[^>]+>", " ", body)
            text = re.sub(r"\s+", " ", text).strip()
            if not text:
                continue
            samples.append(
                Sample(
                    category="meddpicc_summary",
                    output=text,
                    context="",  # transcript not available in note; judge on internal consistency
                    source_id=f"hubspot-note:{rec.get('id')}",
                    timestamp=props.get("hs_timestamp", ""),
                    meta={"note_id": rec.get("id")},
                )
            )
            seen += 1
            if seen >= limit:
                break
        paging = data.get("paging", {})
        after = paging.get("next", {}).get("after")
        if not after or not results:
            break
    print(f"  [hubspot] collected {len(samples)} MEDDPICC notes")
    return samples


# ---------------------------------------------------------------------------
# 2. Pre-call briefs
# ---------------------------------------------------------------------------
def collect_precall_briefs(month: str, limit: int = 50) -> list[Sample]:
    samples: list[Sample] = []
    # From scripts/briefs/ (filename pattern *_YYYY-MM-DD.md)
    pattern = f"*_{month}-*.md"
    files = sorted(glob.glob(str(BRIEFS_DIR / pattern)))
    for fp in files:
        if len(samples) >= limit:
            break
        try:
            text = Path(fp).read_text()
        except Exception:
            continue
        if not text.strip():
            continue
        name = Path(fp).stem
        samples.append(
            Sample(
                category="precall_brief",
                output=text,
                context="",  # briefs are self-contained; judge coherence/grounding in account data
                source_id=f"brief:{name}",
                timestamp=name.split("_")[-1] if "_" in name else "",
                meta={"file": fp},
            )
        )
    # Fall back to account-knowledge synthesis if briefs are thin
    if len(samples) < limit:
        for fp in sorted(ACCOUNT_KNOWLEDGE_DIR.glob("*.md")):
            if len(samples) >= limit:
                break
            try:
                text = Path(fp).read_text()
            except Exception:
                continue
            if "## Synthesis" not in text:
                continue
            # Only include if it has actual content
            synth = text.split("## Synthesis", 1)[-1].strip()
            if len(synth) < 200:
                continue
            samples.append(
                Sample(
                    category="precall_brief",
                    output=text,
                    context="",
                    source_id=f"account-knowledge:{Path(fp).stem}",
                    timestamp="",
                    meta={"file": str(fp)},
                )
            )
    print(f"  [briefs] collected {len(samples)} pre-call briefs")
    return samples


# ---------------------------------------------------------------------------
# 3. Slack replies from session logs
# ---------------------------------------------------------------------------
def _iter_session_files(month: str):
    """Yield session .jsonl files that contain activity in the given month."""
    prefix = f"{month}-"
    for fp in SESSIONS_DIR.glob("*.jsonl"):
        if ".trajectory" in fp.name:
            continue
        yield fp


def collect_slack_replies(month: str, limit: int = 50) -> list[Sample]:
    samples: list[Sample] = []
    # Scan session logs for message tool sends (Slack replies)
    for fp in _iter_session_files(month):
        if len(samples) >= limit:
            break
        try:
            with open(fp) as f:
                for line in f:
                    if len(samples) >= limit:
                        break
                    if '"name":"message"' not in line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    msg = rec.get("message", {})
                    content = msg.get("content", [])
                    if not isinstance(content, list):
                        continue
                    for item in content:
                        if not isinstance(item, dict) or item.get("type") != "toolCall":
                            continue
                        if item.get("name") != "message":
                            continue
                        args = item.get("arguments", {})
                        if not isinstance(args, dict):
                            continue
                        if args.get("action") != "send":
                            continue
                        if args.get("channel") != "slack":
                            continue
                        text = args.get("message", "")
                        if not text or len(text) < 20:
                            continue
                        ts = rec.get("timestamp", "")
                        if not ts.startswith(month):
                            continue
                        samples.append(
                            Sample(
                                category="slack_reply",
                                output=text,
                                context="",  # prior conversation not captured; judge clarity/relevance
                                source_id=f"session:{Path(fp).stem}:{item.get('id','')}",
                                timestamp=ts,
                                meta={"session": Path(fp).stem, "target": args.get("target", "")},
                            )
                        )
        except Exception as e:
            print(f"  [slack] error reading {fp.name}: {e}")
    print(f"  [slack] collected {len(samples)} slack replies")
    return samples


# ---------------------------------------------------------------------------
# 4. Structured JSON writes (HubSpot/Linear via exec in session logs)
# ---------------------------------------------------------------------------
def collect_structured_writes(month: str, limit: int = 50) -> list[Sample]:
    """Collect samples where the GTM agent's DELIVERABLE is a structured JSON write to
    HubSpot or Linear — i.e. an actual POST/PUT/PATCH with a JSON body, or a
    Python/Node script whose purpose is creating/updating CRM objects.

    F4 fix (2026-09-23): the old patterns matched any exec command merely
    containing 'hubspot' + 'create' or a bare GET to crm/v3/objects — that
    swept in read-only queries and bash for-loops, which the judge then
    graded as malformed JSON. Now we require:
      1. an explicit write method (POST/PUT/PATCH/DELETE) to a CRM/Linear
         endpoint, OR a python/node heredoc that performs requests.post/
         patch/put against those endpoints, AND
      2. a JSON payload marker in the command ("json.dumps", "--data",
         "-d '", '"inputs"', '"properties"', '"fields"').
    Read-only GETs, search calls, and associative listing loops are excluded.
    """
    samples: list[Sample] = []
    write_method = re.compile(r"\b(POST|PUT|PATCH|DELETE)\b", re.IGNORECASE)
    write_endpoints = [
        re.compile(r"crm/v\d+/objects/(companies|contacts|deals|notes|tasks|line_items)", re.IGNORECASE),
        re.compile(r"crm/v\d+/objects/[^/]+/batch/(create|update|archive)", re.IGNORECASE),
        re.compile(r"engagements/v\d+", re.IGNORECASE),
        re.compile(r"api\.linear\.app", re.IGNORECASE),
        re.compile(r"issueCreate|commentCreate|issueUpdate", re.IGNORECASE),
    ]
    payload_markers = [
        re.compile(r"json\.dumps", re.IGNORECASE),
        re.compile(r"--data|--data-raw|--data-binary", re.IGNORECASE),
        re.compile(r"-d\s+['\"]\{", re.IGNORECASE),
        re.compile(r"\"(properties|inputs|fields|batchInput)\"\s*:", re.IGNORECASE),
        re.compile(r"requests\.(post|put|patch|delete)\(", re.IGNORECASE),
    ]
    read_only_patterns = [
        re.compile(r"/search", re.IGNORECASE),  # HubSpot search API uses POST but is a read
        re.compile(r"curl[^|]*-X\s*GET", re.IGNORECASE),
        re.compile(r"requests\.get\(", re.IGNORECASE),
        re.compile(r"\bGET\b.*api\.hubapi\.com", re.IGNORECASE),
        re.compile(r"/associations/", re.IGNORECASE),  # association listing is a read
    ]
    skip_patterns = [
        re.compile(r"memory/\d{4}-\d{2}-\d{2}\.md", re.IGNORECASE),
        re.compile(r"cat .*SKILL\.md", re.IGNORECASE),
        re.compile(r"head |tail |grep ", re.IGNORECASE),
    ]
    for fp in _iter_session_files(month):
        if len(samples) >= limit:
            break
        try:
            with open(fp) as f:
                for line in f:
                    if len(samples) >= limit:
                        break
                    if '"name":"exec"' not in line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    msg = rec.get("message", {})
                    content = msg.get("content", [])
                    if not isinstance(content, list):
                        continue
                    for item in content:
                        if not isinstance(item, dict) or item.get("type") != "toolCall":
                            continue
                        if item.get("name") != "exec":
                            continue
                        args = item.get("arguments", {})
                        if not isinstance(args, dict):
                            continue
                        cmd = args.get("command", "")
                        # F4: require an explicit write call directed at a
                        # CRM/Linear endpoint with a JSON payload. Read-only
                        # scripts that merely mention POST somewhere (e.g. a
                        # search call) or use requests.get() are excluded.
                        if any(p.search(cmd) for p in skip_patterns):
                            continue
                        is_read_only = any(p.search(cmd) for p in read_only_patterns)
                        # A write must pair a write-method regex with a CRM
                        # endpoint in the SAME request expression. We look for
                        # at least one of these concrete shapes:
                        #   curl ... -X POST|PUT|PATCH|DELETE ... <endpoint>
                        #   requests.post|put|patch|delete( ... <endpoint>
                        #   POST /crm/... or issueCreate/commentCreate
                        concrete_write = False
                        for m in re.finditer(
                            r"(?:-X\s*(?:POST|PUT|PATCH|DELETE)|requests\.(?:post|put|patch|delete)\()",
                            cmd,
                            re.IGNORECASE,
                        ):
                            window = cmd[m.start() : m.start() + 400]
                            if any(p.search(window) for p in write_endpoints):
                                concrete_write = True
                                break
                        if not concrete_write:
                            # GraphQL-style writes (Linear mutations)
                            if any(p.search(cmd) for p in [
                                re.compile(r"issueCreate|commentCreate|issueUpdate", re.IGNORECASE),
                            ]):
                                concrete_write = True
                        if not concrete_write:
                            continue
                        has_payload = any(p.search(cmd) for p in payload_markers)
                        if not has_payload:
                            continue
                        # A read-only call (search, associations list, plain GET)
                        # is never a structured write, even if it carries a payload.
                        if is_read_only:
                            continue
                        ts = rec.get("timestamp", "")
                        if not ts.startswith(month):
                            continue
                        samples.append(
                            Sample(
                                category="structured_write",
                                output=cmd,
                                context="",
                                expected="",
                                source_id=f"session:{Path(fp).stem}:{item.get('id','')}",
                                timestamp=ts,
                                meta={"session": Path(fp).stem},
                            )
                        )
        except Exception as e:
            print(f"  [writes] error reading {fp.name}: {e}")
    print(f"  [writes] collected {len(samples)} structured write commands")
    return samples


def collect_all(month: str, per_category: int = 50) -> dict[str, list[Sample]]:
    print(f"Collecting the GTM agent outputs for month {month} (limit {per_category}/category)...")
    return {
        "meddpicc_summary": collect_hubspot_notes(month, per_category),
        "precall_brief": collect_precall_briefs(month, per_category),
        "slack_reply": collect_slack_replies(month, per_category),
        "structured_write": collect_structured_writes(month, per_category),
    }
