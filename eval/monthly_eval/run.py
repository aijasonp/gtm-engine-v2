#!/usr/bin/env python3
"""GTM agent monthly evaluation runner.

Samples the GTM agent outputs from the prior calendar month, scores them on
faithfulness/hallucination/task-completion/JSON-correctness/answer-relevancy
using DeepEval (which wraps Ragas) with the {{COMPANY}} gateway as judge, and
produces a structured report.

Usage:
    python monthly_eval/run.py [--month YYYY-MM] [--per-category N] [--judge MODEL]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collectors import collect_all
from evaluator import run_evaluation
from reporting import write_reports


def prior_month() -> str:
    now = datetime.now(timezone.utc)
    first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev = first_this - timedelta(days=1)
    return prev.strftime("%Y-%m")


def main() -> int:
    ap = argparse.ArgumentParser(description="GTM agent monthly evaluation runner")
    ap.add_argument("--month", default=None, help="YYYY-MM (default: prior calendar month)")
    ap.add_argument("--per-category", type=int, default=50,
                    help="max samples per category (default 50)")
    ap.add_argument("--judge", default="claude-sonnet-4-6",
                    help="{{COMPANY}} judge model (default claude-sonnet-4-6)")
    args = ap.parse_args()

    month = args.month or prior_month()
    print(f"GTM agent monthly evaluation for {month}")
    print(f"Judge model: {args.judge} ({{COMPANY}} gateway)")

    data = collect_all(month, per_category=args.per_category)
    total = sum(len(v) for v in data.values())
    if total == 0:
        print("No samples collected for this month. Nothing to evaluate.")
        return 1

    report = run_evaluation(data, judge_model=args.judge)
    json_path, md_path = write_reports(month, report)

    print("\n=== OVERALL SCORES ===")
    for m, score in report["overall"].items():
        print(f"  {m}: {score:.3f}")
    print(f"\nJSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
