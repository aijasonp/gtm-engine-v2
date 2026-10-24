#!/usr/bin/env python3
"""
Banned-phrase scanner for the GTM agent regression tests.

Reads the banned-phrase list from argv[1] (one phrase per line, lowercase)
and the candidate output from stdin. Reports any banned phrase found
(case-insensitive). Exits 0 on pass, 1 on fail. Prints a JSON report.
"""
import json
import sys


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"pass": False, "problems": ["no banned-phrase file provided"]}))
        sys.exit(1)
    with open(sys.argv[1]) as f:
        phrases = [line.strip().lower() for line in f
                   if line.strip() and not line.strip().startswith("#")]
    text = sys.stdin.read()
    low = text.lower()
    hits = []
    for phrase in phrases:
        if phrase in low:
            hits.append(phrase)
    report = {"pass": len(hits) == 0, "banned_phrases_found": hits}
    print(json.dumps(report))
    sys.exit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
