"""Generate JSON + markdown reports from evaluation results."""
from __future__ import annotations
import os

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORTS_DIR = Path(os.path.expanduser("~/.openclaw/workspace/projects/gtm-agent-eval/reports"))

CATEGORY_LABELS = {
    "meddpicc_summary": "MEDDPICC Call Summaries (HubSpot)",
    "precall_brief": "Pre-Call Briefs",
    "slack_reply": "Slack Replies (#gtm-agent / DMs)",
    "structured_write": "Structured JSON Writes (HubSpot/Linear)",
}

METRIC_LABELS = {
    "faithfulness": "Faithfulness",
    "hallucination": "Hallucination (lower is better)",
    "task_completion": "Task Completion",
    "answer_relevancy": "Answer Relevancy",
    "json_correctness": "JSON Correctness",
}


def _load_prior_report(month: str) -> dict | None:
    """Load the previous month's report for MoM delta, if it exists."""
    y, m = int(month[:4]), int(month[5:7])
    if m == 1:
        prev = f"{y-1}-12"
    else:
        prev = f"{y}-{m-1:02d}"
    path = REPORTS_DIR / f"{prev}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return None
    return None


def _top_lowest(report: dict, n: int = 5) -> list[dict]:
    """Top N lowest-scoring samples across all metrics (for human review)."""
    rows = report.get("per_sample", [])
    scored = []
    for r in rows:
        # Use the minimum metric score as the "weakness" signal
        metric_scores = {
            k: v for k, v in r.items()
            if k in METRIC_LABELS and isinstance(v, (int, float))
        }
        if not metric_scores:
            continue
        min_score = min(metric_scores.values())
        scored.append({**r, "_min_score": min_score})
    scored.sort(key=lambda x: x["_min_score"])
    return scored[:n]


def write_reports(month: str, report: dict) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"{month}.json"
    md_path = REPORTS_DIR / f"{month}.md"

    # JSON report
    json_path.write_text(json.dumps(report, indent=2, default=str))

    # Markdown report
    prior = _load_prior_report(month)
    lines = []
    lines.append(f"# GTM agent Monthly Evaluation — {month}")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_")
    lines.append(f"_Judge model: `{report.get('judge_model', 'n/a')}` ({{COMPANY}} gateway)_")
    lines.append("")
    lines.append("## Overall Scores")
    lines.append("")
    lines.append("| Metric | Score | MoM Δ |")
    lines.append("|--------|-------|-------|")
    for m, score in report.get("overall", {}).items():
        delta = ""
        if prior and m in prior.get("overall", {}):
            d = score - prior["overall"][m]
            delta = f"{d:+.3f}"
        lines.append(f"| {METRIC_LABELS.get(m, m)} | {score:.3f} | {delta} |")
    lines.append("")

    lines.append("## Per-Category Breakdown")
    lines.append("")
    for cat, agg in report.get("per_category", {}).items():
        label = CATEGORY_LABELS.get(cat, cat)
        lines.append(f"### {label} ({agg.get('count', 0)} samples)")
        lines.append("")
        scores = agg.get("scores", {})
        if not scores:
            lines.append("_No samples evaluated._")
            lines.append("")
            continue
        lines.append("| Metric | Mean | Min | Max |")
        lines.append("|--------|------|-----|-----|")
        for m, stats in scores.items():
            lines.append(
                f"| {METRIC_LABELS.get(m, m)} | {stats['mean']:.3f} | "
                f"{stats['min']:.3f} | {stats['max']:.3f} |"
            )
        lines.append("")

    lines.append("## Top 5 Lowest-Scoring Outputs (for human review)")
    lines.append("")
    lowest = _top_lowest(report, 5)
    if not lowest:
        lines.append("_No scored samples._")
    else:
        for i, r in enumerate(lowest, 1):
            cat = CATEGORY_LABELS.get(r.get("category", ""), r.get("category", ""))
            lines.append(f"### {i}. {cat}")
            lines.append("")
            lines.append(f"- **Source:** `{r.get('source_id', 'n/a')}`")
            lines.append(f"- **Timestamp:** {r.get('timestamp', 'n/a')}")
            metric_scores = {
                k: f"{v:.2f}" for k, v in r.items()
                if k in METRIC_LABELS and isinstance(v, (int, float))
            }
            lines.append(f"- **Scores:** {metric_scores}")
            preview = (r.get("output_preview") or "")[:300]
            lines.append(f"- **Output preview:** {preview}")
            lines.append("")
    md_path.write_text("\n".join(lines))
    return json_path, md_path
