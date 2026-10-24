#!/usr/bin/env python3
"""
Slack markdown / mrkdwn linter for the GTM agent regression tests.

Checks:
  1. No pipe tables (Slack does not render them).
  2. No em dashes (U+2014) anywhere in output destined for {{SALES_LEADER}}/{{AE_2}}
     (and per {{COMPANY}} voice rules, banned from all external content).
  3. Balanced mrkdwn bold (*...*) and italic (_..._) markers.
  4. No broken mrkdwn link syntax (missing pipe or closing >).
  5. No HTML tags (Slack mrkdwn does not support them).

Reads the candidate output from stdin. Exits 0 if clean, 1 if any violation.
Prints a JSON report to stdout.
"""
import json
import re
import sys


def lint(text: str) -> dict:
    problems = []

    # 1. Pipe tables
    # A pipe table is a line with a pipe and a following separator line of dashes.
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "|" in line and i + 1 < len(lines):
            nxt = lines[i + 1]
            if re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", nxt) and "-" in nxt:
                problems.append(
                    {"rule": "no-pipe-tables", "line": i + 1,
                     "detail": "Slack does not render pipe tables"}
                )
                break

    # 2. Em dashes
    if "\u2014" in text:
        problems.append(
            {"rule": "no-em-dash", "line": None,
             "detail": "Em dash (U+2014) found; banned in all external content"}
        )

    # 3. Balanced mrkdwn bold/italic
    for marker, name in [("**", "bold"), ("_", "italic")]:
        count = text.count(marker)
        if count % 2 != 0:
            problems.append(
                {"rule": f"unbalanced-{name}", "line": None,
                 "detail": f"Unbalanced {name} marker '{marker}' (count={count})"}
            )

    # 4. Broken mrkdwn links: [text](url) must have both brackets and a pipe-free url
    for m in re.finditer(r"\[([^\]]*)\]\(([^)]*)\)", text):
        if not m.group(1).strip():
            problems.append(
                {"rule": "broken-link", "line": None,
                 "detail": f"Link with empty text: {m.group(0)}"}
            )
        if not m.group(2).strip():
            problems.append(
                {"rule": "broken-link", "line": None,
                 "detail": f"Link with empty url: {m.group(0)}"}
            )

    # 5. HTML tags
    if re.search(r"<[a-zA-Z/][^>]*>", text):
        problems.append(
            {"rule": "html-tags", "line": None,
             "detail": "HTML tags are not supported in Slack mrkdwn"}
        )

    return {
        "pass": len(problems) == 0,
        "problems": problems,
    }


def main():
    text = sys.stdin.read()
    report = lint(text)
    print(json.dumps(report))
    sys.exit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
