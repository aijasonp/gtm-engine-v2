#!/usr/bin/env python3
"""Fail if any former-employer or internal identifier appears in the repo or a build.

    python3 scripts/check_clean.py [path ...]     # default: the whole repo

The patterns are stored base64-encoded so this file does not itself contain
the identifiers it blocks. Add a pattern with:
    python3 -c "import base64;print(base64.b64encode(br'pattern').decode())"
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

ENCODED = [
    "a2luZG8=",
    "dXNhYmxlID9tYWNoaW5lcw==",
    "XGJvZGlua1xi",
    "XGJvZGluIGtcYg==",
    "XGJhcnJ0eVxi",
    "XGJhaXJlb25cYg==",
    "ZGVlcGhhdA==",
    "d2hpdGVyYWJiaXRuZW8=",
    "cmV0cmlldmFsLTk=",
    "bWFjLXN0dWRpby0xMA==",
    "MTBcLjEwMFwuMjZcLg==",
    "XGJqYW5pY2FcYg==",
    "dmFyZ2hlc2U=",
    "dG9tIG1pdGNoZWxs",
    "aGFnZ2V0dA==",
    "XGJsYXZlbGxlXGI=",
    "bWNtYWhvbg==",
    "bmV6YXJhdGk=",
    "c2VmYS1ib2FreWU=",
    "Y2xhd3NtaXRo",
    "b3BlbmNsYXctYWdlbnQ=",
    "MWxyME1EYXQ=",
    "MTRHYS1iRzA=",
    "MjM4NjA5OTU=",
    "NjdlNTYyOTEyMzk0MGQyNDJlZjM5Mjkx",
    "XGJkb2lua1xi",
    "amFydmlzIGtcYg==",
    "YmFlcnN0",
    "YWxpZ25lZCBkYXRhIGNlbnRlcnM=",
    "bWFzdGVyY29udHJvbA==",
    "ZXh0cmFob3A=",
    "c3RhdGlvbiBjYXNpbm9z",
    "XGJ2dWx0clxi",
    "dG9tLXByb3NwZWN0",
    "bWF0dC1iZWNr",
    "amVhbmV0dGU=",
    "IzYzMjBFOA==",
    "IzBEMEIxNQ==",
    "ZWxlY3RyaWNbIF9daW5kaWdv",
    "dGVjaFsgX11ibGFjaw==",
    "XGJzZWFzYWx0XGI=",
    "YXNwZWt0YQ==",
    "bWFjaGluZSBzcGVlZA==",
    "XGJTTUtcYg==",
]
PATTERNS = [re.compile(base64.b64decode(e).decode(), re.I) for e in ENCODED]
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", ".venv", "dist"}
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".woff", ".woff2", ".ttf", ".otf", ".zip", ".db"}


def scan(root: Path) -> list[str]:
    root = Path(root)
    hits = []
    files = [root] if root.is_file() else root.rglob("*")
    for f in files:
        if not f.is_file() or f.suffix.lower() in BINARY:
            continue
        if f != root and any(part in SKIP_DIRS for part in f.relative_to(root).parts[:-1]):
            continue
        for i, pat in enumerate(PATTERNS):
            if pat.search(str(f.name)):
                hits.append(f"{f} (file name, pattern #{i})")
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for i, pat in enumerate(PATTERNS):
                if pat.search(line):
                    hits.append(f"{f}:{n} (pattern #{i})")
    return hits


def main(argv: list[str]) -> int:
    roots = [Path(p) for p in argv] or [Path(__file__).resolve().parents[1]]
    hits = [h for r in roots for h in scan(r)]
    for h in hits:
        print(h)
    print(f"{len(hits)} banned identifiers found" if hits else "clean: 0 banned identifiers")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
