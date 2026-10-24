#!/usr/bin/env python3
"""
Before/after comparison for the DSPy+GEPA prompt optimization layer.

Loads the baseline (unoptimized) and optimized programs for each task, runs both
on the training examples, and prints a table:
    task | baseline score | optimized score | delta
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DSPY_GEPA_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = PROJECT_ROOT / "promptfoo" / "fixtures"
OPTIMIZED_DIR = DSPY_GEPA_DIR / "optimized"

sys.path.insert(0, str(DSPY_GEPA_DIR))

import optimizer as opt  # noqa: E402  (loads env, configures dspy)


def load_optimized_prompts() -> dict[str, str]:
    """Load the optimized system prompt for each task from saved JSON."""
    prompts = {}
    for task_name in ["meddpicc", "slack", "json", "brand", "isolation"]:
        p = OPTIMIZED_DIR / f"{task_name}.json"
        if p.exists():
            data = json.loads(p.read_text())
            prompts[task_name] = data.get("best_prompt", "")
        else:
            print(f"WARNING: no optimized program found for {task_name} at {p}")
            prompts[task_name] = ""
    return prompts


def score_with_prompt(task_name: str, prompt: str, examples: list) -> float:
    """Score a system prompt on the training examples using the task metric."""
    return opt._score_prompt(task_name, prompt, examples)


def main() -> None:
    training = opt.load_training_data()
    optimized_prompts = load_optimized_prompts()

    print("=" * 70)
    print("DSPy+GEPA before/after comparison")
    print("=" * 70)
    print(f"{'task':<12}{'baseline':<12}{'optimized':<12}{'delta':<10}")

    rows = []
    for task_name in ["meddpicc", "slack", "json", "brand", "isolation"]:
        examples = training[task_name]
        baseline_prompt = opt._baseline_prompt(task_name)
        optimized_prompt = optimized_prompts.get(task_name, "")

        baseline_score = score_with_prompt(task_name, baseline_prompt, examples)
        if optimized_prompt:
            optimized_score = score_with_prompt(task_name, optimized_prompt, examples)
        else:
            optimized_score = baseline_score

        delta = optimized_score - baseline_score
        rows.append((task_name, baseline_score, optimized_score, delta))
        print(
            f"{task_name:<12}{baseline_score:<12.3f}{optimized_score:<12.3f}"
            f"{delta:<+10.3f}"
        )

    print("\nNote: scores are on the training set (2 examples per task).")
    print("Optimized should be >= baseline. If a task shows no improvement, the")
    print("baseline may already be near-perfect on these fixtures.")


if __name__ == "__main__":
    main()
