#!/usr/bin/env python3
"""PreToolUse(WebSearch): append the current year to a query that has no time anchor.

The earlier inline version returned `modifiedToolInput`, which is not a hooks API
field, so it never changed a query. The documented field is
`hookSpecificOutput.updatedInput`, and it REPLACES the whole tool input, so every
original field is carried over and only `query` changes.

    python3 websearch-year.py --selftest
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime

TEMPORAL = ("latest", "recent", "current", "new", "now", "today")


def rewrite(query: str, year: str) -> str | None:
    """The new query, or None when the query already carries a time anchor."""
    if not query or re.search(r"\b20\d{2}\b", query):
        return None
    if any(re.search(rf"\b{w}\b", query.lower()) for w in TEMPORAL):
        return None
    return f"{query} {year}"


def decide(payload: dict, year: str) -> dict | None:
    tool_input = payload.get("tool_input") or {}
    new = rewrite(tool_input.get("query", ""), year)
    if new is None:
        return None
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": f"websearch-year: appended {year}",
        "updatedInput": {**tool_input, "query": new},
    }}


def selftest() -> int:
    ok = True

    def check(label, cond):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")
        ok = ok and cond

    out = decide({"tool_input": {"query": "claude code hooks", "allowed_domains": ["a.com"]}}, "2026")
    check("bare query gets the year", out and out["hookSpecificOutput"]["updatedInput"]["query"] == "claude code hooks 2026")
    check("other input fields survive", out and out["hookSpecificOutput"]["updatedInput"].get("allowed_domains") == ["a.com"])
    check("uses updatedInput, not modifiedToolInput", out and "modifiedToolInput" not in out["hookSpecificOutput"])
    check("query with a year is left alone", decide({"tool_input": {"query": "gpt 2025 review"}}, "2026") is None)
    check("query with 'latest' is left alone", decide({"tool_input": {"query": "latest vllm release"}}, "2026") is None)
    check("'newsletter' is not the word 'new'", decide({"tool_input": {"query": "newsletter tools"}}, "2026") is not None)
    check("empty input is left alone", decide({}, "2026") is None)
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    try:
        out = decide(json.load(sys.stdin), str(datetime.now().year))
    except Exception:
        sys.exit(0)  # fail open: a search helper must never block a search
    if out:
        print(json.dumps(out))
    sys.exit(0)
