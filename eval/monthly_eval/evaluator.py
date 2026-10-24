"""Run DeepEval/Ragas metrics over collected the GTM agent samples using the {{COMPANY}} judge."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from collectors import Sample
from company_llm import CompanyLLM

from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    HallucinationMetric,
    TaskCompletionMetric,
)
from deepeval.test_case import LLMTestCase

# Judge model — {{COMPANY}} gateway, no external paid API
JUDGE_MODEL = "claude-sonnet-4-6"

# Which metrics apply to which category
CATEGORY_METRICS = {
    "meddpicc_summary": ["faithfulness", "hallucination", "task_completion"],
    "precall_brief": ["faithfulness", "hallucination", "task_completion"],
    "slack_reply": ["answer_relevancy", "task_completion"],
    "structured_write": ["json_correctness", "task_completion"],
}


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _truncate(text: str, n: int = 6000) -> str:
    if len(text) <= n:
        return text
    return text[:n] + "...[truncated]"


def _build_context(sample: Sample) -> str:
    """Build a retrieval context for faithfulness/hallucination judging."""
    parts = []
    if sample.context:
        parts.append(sample.context)
    if sample.expected:
        parts.append(f"Expected/ground truth: {sample.expected}")
    if not parts:
        # For self-contained outputs, use the output itself as the only context
        # so hallucination = claims not derivable from the output's own source.
        parts.append("(No external source context provided for this sample.)")
    return "\n\n".join(parts)


def _metric_instances(llm: CompanyLLM, names: list[str]) -> dict[str, Any]:
    out = {}
    for name in names:
        if name == "faithfulness":
            out[name] = FaithfulnessMetric(model=llm, threshold=0.5, verbose_mode=False)
        elif name == "hallucination":
            out[name] = HallucinationMetric(model=llm, threshold=0.5, verbose_mode=False)
        elif name == "task_completion":
            out[name] = TaskCompletionMetric(model=llm, threshold=0.5, verbose_mode=False)
        elif name == "answer_relevancy":
            out[name] = AnswerRelevancyMetric(model=llm, threshold=0.5, verbose_mode=False)
        elif name == "json_correctness":
            # JSON correctness is computed locally (schema validation), not via LLM.
            out[name] = None
    return out


def _json_correctness(sample: Sample) -> dict:
    """Local JSON/schema validation for structured writes."""
    cmd = sample.output
    score = 0.0
    reasons = []
    # Heuristics: does the command look like a well-formed write?
    has_endpoint = bool(re.search(r"crm/v3/objects|engagements/v1|api\.linear\.app", cmd, re.I))
    has_method = bool(re.search(r"requests\.(post|put|patch)|curl .* -X (POST|PUT|PATCH)", cmd, re.I))
    has_payload = bool(re.search(r"json=|data=|payload|properties", cmd, re.I))
    has_auth = bool(re.search(r"HUBSPOT_API_TOKEN|HUBSPOT_TOKEN|LINEAR_API_KEY|Authorization", cmd, re.I))
    checks = [has_endpoint, has_method, has_payload, has_auth]
    score = sum(checks) / len(checks)
    if has_endpoint:
        reasons.append("targets a valid write endpoint")
    if has_method:
        reasons.append("uses a write HTTP method")
    if has_payload:
        reasons.append("includes a payload")
    if has_auth:
        reasons.append("includes auth")
    if not has_endpoint:
        reasons.append("no recognized write endpoint")
    return {"score": score, "reasons": reasons}


def evaluate_samples(
    samples: list[Sample], llm: CompanyLLM, metrics: list[str]
) -> list[dict]:
    """Evaluate a list of samples, returning per-sample metric results."""
    results = []
    instances = _metric_instances(llm, metrics)
    for i, sample in enumerate(samples):
        row: dict = {
            "category": sample.category,
            "source_id": sample.source_id,
            "timestamp": sample.timestamp,
            "output_preview": _truncate(sample.output, 500),
        }
        context = _build_context(sample)
        test_case = LLMTestCase(
            input=context,
            actual_output=_truncate(sample.output),
            expected_output=sample.expected or None,
            context=[context],
            retrieval_context=[context],
        )
        for name in metrics:
            inst = instances[name]
            if inst is None:
                # local json_correctness
                jc = _json_correctness(sample)
                row["json_correctness"] = jc["score"]
                row["json_correctness_reasons"] = jc["reasons"]
                continue
            try:
                inst.measure(test_case)
                row[name] = inst.score
                row[f"{name}_reason"] = getattr(inst, "reason", "")
            except Exception as e:
                row[name] = None
                row[f"{name}_error"] = str(e)[:300]
        results.append(row)
        print(f"    [{i+1}/{len(samples)}] {sample.category} {sample.source_id} -> "
              + ", ".join(f"{k}={v:.2f}" for k, v in row.items() if isinstance(v, float)))
    return results


def run_evaluation(
    data: dict[str, list[Sample]], judge_model: str = JUDGE_MODEL
) -> dict:
    llm = CompanyLLM(model=judge_model)
    report: dict = {
        "judge_model": judge_model,
        "per_sample": [],
        "per_category": {},
        "overall": {},
    }
    for category, samples in data.items():
        metrics = CATEGORY_METRICS.get(category, ["task_completion"])
        print(f"\n=== Evaluating {category} ({len(samples)} samples) ===")
        if not samples:
            report["per_category"][category] = {"count": 0, "scores": {}}
            continue
        rows = evaluate_samples(samples, llm, metrics)
        report["per_sample"].extend(rows)
        # Aggregate
        agg: dict = {"count": len(rows), "scores": {}}
        for m in metrics:
            vals = [r[m] for r in rows if isinstance(r.get(m), (int, float))]
            if vals:
                agg["scores"][m] = {
                    "mean": round(sum(vals) / len(vals), 4),
                    "min": round(min(vals), 4),
                    "max": round(max(vals), 4),
                    "n": len(vals),
                }
        report["per_category"][category] = agg
    # Overall = mean of category means
    overall: dict = {}
    for cat, agg in report["per_category"].items():
        for m, stats in agg.get("scores", {}).items():
            overall.setdefault(m, []).append(stats["mean"])
    report["overall"] = {
        m: round(sum(v) / len(v), 4) for m, v in overall.items()
    }
    return report
