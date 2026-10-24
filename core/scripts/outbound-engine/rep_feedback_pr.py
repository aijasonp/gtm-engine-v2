#!/usr/bin/env python3
"""
rep_feedback_pr.py: open a PR for a rep-feedback record stored in
gtm-vault/feedback/rep-feedback/.

HARD SCOPE: this script only opens PRs against the single repo named in
FEEDBACK_REPO (owner/name), set once at deploy time. It is not a CLI
argument. If FEEDBACK_REPO is unset the script refuses before auth or
network I/O.

Environment:
    FEEDBACK_REPO       owner/name of the only repo PRs may target (required)
    FEEDBACK_REPO_DIR   local clone of that repo (default ~/.gtm/repos/feedback)
    GTM_WORKSPACE       agent workspace root (default ~/.gtm/workspace)
    FEEDBACK_REVIEWER   name shown in the PR footer (default "the GTM owner")

Usage:
    python3 rep_feedback_pr.py <path-to-feedback-md> [--dry-run]

Exit codes:
    0  PR opened (or dry-run ok)
    2  target repo not allowlisted
    3  feedback file invalid / missing required fields
    4  gh CLI error
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# HARD ALLOWLIST: one repo, fixed by deploy-time environment, never a CLI flag.
ALLOWED_REPO = os.environ.get("FEEDBACK_REPO", "").strip()

WORKSPACE = Path(os.path.expanduser(os.environ.get("GTM_WORKSPACE", "~/.gtm/workspace")))
FEEDBACK_DIR = WORKSPACE / "gtm-vault" / "feedback" / "rep-feedback"
# Local clone of the allowlisted repo. PRs are opened from here, never from the workspace.
REPO_DIR = Path(os.path.expanduser(os.environ.get("FEEDBACK_REPO_DIR", "~/.gtm/repos/feedback")))
REVIEWER = os.environ.get("FEEDBACK_REVIEWER", "the GTM owner")

REQUIRED_FIELDS = ("Reported (UTC)", "Reporter", "Type", "Details")


def fail(msg: str, code: int) -> "NoReturn":  # type: ignore[name-defined]
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_feedback(path: Path) -> dict:
    if not path.exists():
        fail(f"feedback file not found: {path}", 3)
    text = path.read_text(encoding="utf-8")
    for field in REQUIRED_FIELDS:
        if field not in text:
            fail(f"feedback file missing required field '{field}': {path}", 3)

    def grab(label: str) -> str:
        m = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.+)", text)
        return m.group(1).strip() if m else ""

    # Title: prefer the descriptive filename stem; H1 in these records is generic ("Rep Feedback").
    # Filename format: YYYY-MM-DD-<slug>.md → humanize the slug.
    stem = path.stem
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-?", "", stem).replace("-", " ").strip()
    h1 = re.search(r"^#\s+(.+)$", text, flags=re.M)
    h1_title = h1.group(1).strip() if h1 else ""
    title = slug if slug else (h1_title or stem)

    return {
        "title": title,
        "reported": grab("Reported (UTC)"),
        "reporter": grab("Reporter"),
        "type": grab("Type"),
        "company": grab("Company / Domain"),
        "campaign": grab("Campaign"),
        "thread": grab("Slack thread"),
        "body_md": text,
    }


def build_pr_body(meta: dict, source_path: Path) -> str:
    rel = source_path.relative_to(WORKSPACE)
    return (
        f"## Rep Feedback: {meta['title']}\n\n"
        f"- **Reported (UTC):** {meta['reported']}\n"
        f"- **Reporter:** {meta['reporter']}\n"
        f"- **Type:** {meta['type']}\n"
        f"- **Company / Domain:** {meta['company']}\n"
        f"- **Campaign:** {meta['campaign']}\n"
        f"- **Slack thread:** {meta['thread']}\n"
        f"- **Source record:** `{rel}`\n\n"
        f"---\n\n"
        f"{meta['body_md']}\n\n"
        f"---\n"
        f"_Opened by the GTM agent via `outbound-engine/rep_feedback_pr.py`. "
        f"Route: rep feedback → classify → gtm-vault → this PR for {REVIEWER} to review._"
    )


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("feedback_file", help="Path to feedback .md under gtm-vault/feedback/rep-feedback/")
    ap.add_argument("--dry-run", action="store_true", help="Print what would happen; no gh calls")
    args = ap.parse_args()

    # Hard scope guard: refuse unless the deploy-time allowlist is set.
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", ALLOWED_REPO):
        fail("FEEDBACK_REPO is not set to owner/name; refusing to open any PR", 2)
    target_repo = ALLOWED_REPO

    path = Path(args.feedback_file).resolve()
    # Constrain to the feedback dir so we don't PR arbitrary files.
    try:
        path.relative_to(FEEDBACK_DIR.resolve())
    except ValueError:
        fail(f"feedback file must live under {FEEDBACK_DIR}", 3)

    meta = parse_feedback(path)
    pr_title = f"[rep-feedback] {meta['type']}: {meta['title'][:80]}"
    pr_body = build_pr_body(meta, path)
    branch = f"rep-feedback/{path.stem}"

    if args.dry_run:
        print(f"DRY RUN: would open PR in {target_repo}")
        print(f"  branch: {branch}")
        print(f"  title:  {pr_title}")
        print(f"  body:\n{pr_body}")
        return 0

    if not (REPO_DIR / ".git").exists():
        fail(f"repo clone missing at {REPO_DIR}; clone {ALLOWED_REPO} there first", 4)

    dest_rel = Path("gtm-vault") / "feedback" / "rep-feedback" / path.name

    # Order matters: reset the branch from origin/main FIRST, then write the file.
    # Writing before checkout loses the file when the branch is reset (tracked-in-old-HEAD
    # files get removed on reset). Idempotent: re-running the same record is a no-op commit.
    pre = [
        ["git", "-C", str(REPO_DIR), "fetch", "origin", "main"],
        ["git", "-C", str(REPO_DIR), "checkout", "-B", branch, "origin/main"],
    ]
    for cmd in pre:
        proc = run(cmd)
        if proc.returncode != 0:
            print(f"ERROR running: {' '.join(cmd)}", file=sys.stderr)
            print(proc.stdout, file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return 4

    dest = REPO_DIR / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    # gh CLI must be authenticated (GitHub App installation token or PAT scoped to FEEDBACK_REPO).
    steps = [
        ["git", "-C", str(REPO_DIR), "add", str(dest_rel)],
        ["git", "-C", str(REPO_DIR), "commit", "-m", pr_title, "--allow-empty"],
        ["git", "-C", str(REPO_DIR), "push", "-u", "origin", branch, "--force"],
        [
            "gh", "pr", "create",
            "--repo", target_repo,
            "--title", pr_title,
            "--body", pr_body,
            "--head", branch,
        ],
    ]
    for cmd in steps:
        proc = run(cmd)
        if proc.returncode != 0:
            print(f"ERROR running: {' '.join(cmd)}", file=sys.stderr)
            print(proc.stdout, file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            return 4
        if cmd[0] == "gh":
            print(proc.stdout.strip())

    return 0


# NOTE: if a PR already exists for the branch, `gh pr create` exits non-zero and the
# script reports the gh stderr (which includes the existing PR URL). That is intentional:
# re-runs surface the existing PR instead of silently opening a duplicate.


if __name__ == "__main__":
    sys.exit(main())
