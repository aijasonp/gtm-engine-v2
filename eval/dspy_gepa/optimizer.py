#!/usr/bin/env python3
"""
DSPy + GEPA prompt optimization layer for the GTM agent eval stack.

Optimizes the 5 promptfoo prompt groups (meddpicc, slack, json, brand, isolation)
against their golden fixtures using GEPA (evolutionary prompt optimization) with
DSPy modules as the baseline programs.

Architecture
------------
- DSPy modules (Signature + Predict/ChainOfThought) define the baseline program for
  each task, with the task rules embedded in the signature docstring.
- GEPA (functional `optimize()` API in gepa 0.1.4) evolves the *system prompt* text
  for each task, scoring candidate prompts with a per-task metric function.
- The optimized prompt (best candidate) is saved to `dspy_gepa/optimized/<task>.json`.

Models ({{COMPANY}} API, OpenAI-compatible)
-------------------------------------
- Generator LM:  openai/gpt-5
- Reflection LM: openai/claude-sonnet-4-6

Usage
-----
    ./dspy_gepa/run.sh
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# --- Path setup -------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # gtm-agent-eval/
DSPY_GEPA_DIR = Path(__file__).resolve().parent
PROMPTFOO_DIR = PROJECT_ROOT / "promptfoo"
FIXTURES_DIR = PROMPTFOO_DIR / "fixtures"
LOGS_DIR = DSPY_GEPA_DIR / "logs"
OPTIMIZED_DIR = DSPY_GEPA_DIR / "optimized"

# --- Load COMPANY_API_KEY -----------------------------------------------------
def load_env() -> None:
    """Load COMPANY_API_KEY from ~/.openclaw/.env if not already set."""
    if os.environ.get("COMPANY_API_KEY"):
        return
    env_path = Path.home() / ".openclaw" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("COMPANY_API_KEY="):
                os.environ["COMPANY_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                return
    raise RuntimeError("COMPANY_API_KEY not found in environment or ~/.openclaw/.env")


load_env()

COMPANY_API_KEY = os.environ["COMPANY_API_KEY"]
COMPANY_BASE = "https://llm.example.com/v1"
GEN_MODEL = "openai/gpt-5"
REFLECT_MODEL = "openai/claude-sonnet-4-6"

# --- DSPy LM configuration --------------------------------------------------
import dspy  # noqa: E402

# litellm drop_params for openai>=2.0 compatibility
try:
    import litellm

    litellm.drop_params = True
except Exception:  # pragma: no cover
    pass

# Generator LM (gpt-5) and reflection LM (claude-sonnet-4-6).
# NOTE: dspy 3.3.1 enforces OpenAI reasoning-model constraints on gpt-5
# (temperature=1.0, max_tokens>=16000). GEPA does the real optimization with its
# own gepa.lm.LM (no such guard); the dspy.LM here is the baseline program LM.
gen_lm = dspy.LM(
    model=GEN_MODEL,
    api_base=COMPANY_BASE,
    api_key=COMPANY_API_KEY,
    max_tokens=16000,
    temperature=1.0,
)
reflect_lm = dspy.LM(
    model=REFLECT_MODEL,
    api_base=COMPANY_BASE,
    api_key=COMPANY_API_KEY,
    max_tokens=1200,
    temperature=0.0,
)

dspy.configure(lm=gen_lm)


# ============================================================================
# 1. DSPy Signatures + Modules (baseline programs)
# ============================================================================
class MEDDPICCSignature(dspy.Signature):
    """You are the GTM agent, {{COMPANY}}'s sales assistant. Read the call transcript and produce a
    MEDDPICC call summary as STRICT JSON with exactly these keys: metrics,
    economicBuyer, decisionCriteria, decisionProcess, paperProcess, identifyPain,
    champion, competition.

    Rules:
    - Only include facts stated in the transcript. Do NOT invent metrics, customer
      names, or dollar figures.
    - If a field is not mentioned, use an empty string "".
    - Output ONLY the JSON object. No markdown fences, no prose, no commentary.
    - Do NOT use em dashes (U+2014).
    """

    transcript: str = dspy.InputField(desc="Call transcript text")
    output: str = dspy.OutputField(desc="MEDDPICC summary as strict JSON with 8 keys")


class SlackSignature(dspy.Signature):
    """You are the GTM agent, {{COMPANY}}'s internal sales assistant. Write a Slack update for the
    channel described in the task.

    Rules:
    - Use Slack mrkdwn formatting: *bold* for emphasis, bullet lists with "-".
    - Do NOT use pipe tables (Slack does not render them).
    - Do NOT use em dashes (U+2014). Use commas, periods, colons, or parentheses.
    - Do NOT use HTML tags.
    - Keep it casual, direct, internal tone. No AI-sounding phrases.
    """

    task: str = dspy.InputField(desc="Slack update task description")
    output: str = dspy.OutputField(desc="Slack mrkdwn text")


class JSONSignature(dspy.Signature):
    """You are the GTM agent, {{COMPANY}}'s sales assistant. Complete the task below.

    Rules:
    - Output ONLY valid JSON. No markdown fences, no prose, no commentary.
    - Match the exact schema requested.
    """

    task: str = dspy.InputField(desc="JSON payload task description")
    output: str = dspy.OutputField(desc="Valid JSON matching the requested schema")


class BrandSignature(dspy.Signature):
    """You are the GTM agent, writing on behalf of {{COMPANY}}, an enterprise agentic security
    company. We build AI agents that run DevOps and SecOps workflows autonomously.
    Model-agnostic, data-sovereign, on-premise or cloud.

    Register: direct, technical, plainspoken. Vary sentence rhythm. Active voice.
    Concrete over abstract. Numbers over adjectives.

    Hard rules:
    - No em dashes. Ever. Use commas, periods, colons, or parentheses.
    - No AI-sounding phrases: revolutionize, game-changing, leverage, synergy,
      cutting-edge, best-in-class, AI-powered, next-generation.
    - No filler words or hedge phrases.
    - Never invent facts. Every statistic and named source must be real.
    """

    task: str = dspy.InputField(desc="Email writing task description")
    output: str = dspy.OutputField(desc="Email text")


class IsolationSignature(dspy.Signature):
    """You are the GTM agent, {{COMPANY}}'s sales assistant. Write a pre-call brief for the meeting
    described below.

    Rules:
    - This brief is scoped to ONE customer only. Do NOT mention any other customer,
      company, or prospect by name anywhere in the output.
    - Do not reference other deals, other customers, or other companies.
    - Stay strictly within the scope of the described customer.
    - Do NOT use em dashes (U+2014). Use commas, periods, colons, or parentheses.
    - Do NOT use AI-sounding phrases (leverage, game-changing, cutting-edge).
    """

    task: str = dspy.InputField(desc="Pre-call brief task description")
    output: str = dspy.OutputField(desc="Pre-call brief text")


# Modules: Predict for JSON tasks, ChainOfThought for text tasks
def build_modules() -> dict[str, dspy.Module]:
    return {
        "meddpicc": dspy.Predict(MEDDPICCSignature),
        "slack": dspy.ChainOfThought(SlackSignature),
        "json": dspy.Predict(JSONSignature),
        "brand": dspy.ChainOfThought(BrandSignature),
        "isolation": dspy.ChainOfThought(IsolationSignature),
    }


# ============================================================================
# 2. Metric functions (example, prediction, trace) -> float 0-1
# ============================================================================
MEDDPICC_KEYS = [
    "metrics", "economicBuyer", "decisionCriteria", "decisionProcess",
    "paperProcess", "identifyPain", "champion", "competition",
]
# Customer names that must NOT appear unless present in the transcript
HALLUCINATED_NAMES = ["Globex", "{{CUSTOMER_D}}", "{{PARTNER_A}}", "AcmeCorp"]
BANNED_PHRASES = [
    "leverage", "synergy", "cutting-edge", "revolutionize", "game-changing",
    "best-in-class", "AI-powered", "next-generation",
]
EM_DASH = "\u2014"


def _clean_json(text: str) -> str:
    """Strip markdown fences and surrounding whitespace from a JSON string."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _parse_json(text: str):
    """Parse JSON from a string, tolerating markdown fences. Returns obj or None."""
    try:
        return json.loads(_clean_json(text))
    except Exception:
        return None


def meddpicc_metric(example, prediction, trace) -> float:
    """MEDDPICC: all 8 keys present, no hallucinated names, no em dashes."""
    checks = []
    out = prediction if isinstance(prediction, str) else str(prediction)
    obj = _parse_json(out)
    if obj is not None and isinstance(obj, dict):
        checks.append(all(k in obj for k in MEDDPICC_KEYS))
    else:
        checks.append(False)
    # No hallucinated customer names (unless in transcript)
    transcript = getattr(example, "transcript", "") or ""
    s = out
    checks.append(not any(n in s for n in HALLUCINATED_NAMES if n not in transcript))
    # No em dashes
    checks.append(EM_DASH not in s)
    return sum(checks) / len(checks)


def slack_metric(example, prediction, trace) -> float:
    """Slack: no pipe tables, no em dashes, no HTML tags."""
    checks = []
    out = prediction if isinstance(prediction, str) else str(prediction)
    checks.append("|" not in out)          # no pipe tables
    checks.append(EM_DASH not in out)      # no em dashes
    checks.append(not re.search(r"<[a-zA-Z/][^>]*>", out))  # no HTML tags
    return sum(checks) / len(checks)


def json_metric(example, prediction, trace) -> float:
    """JSON: 1.0 valid+schema-match, 0.5 valid but schema mismatch, 0.0 unparseable."""
    out = prediction if isinstance(prediction, str) else str(prediction)
    obj = _parse_json(out)
    if obj is None:
        return 0.0
    schema = getattr(example, "schema", None)
    if schema is None:
        return 1.0
    if isinstance(obj, dict):
        required = schema.get("required", [])
        if all(k in obj for k in required):
            return 1.0
    return 0.5


def brand_metric(example, prediction, trace) -> float:
    """Brand: no em dashes, no banned phrases."""
    checks = []
    out = prediction if isinstance(prediction, str) else str(prediction)
    low = out.lower()
    checks.append(EM_DASH not in out)
    checks.append(not any(p in low for p in BANNED_PHRASES))
    return sum(checks) / len(checks)


def isolation_metric(example, prediction, trace) -> float:
    """Isolation: no banned customer names, no em dashes."""
    checks = []
    out = prediction if isinstance(prediction, str) else str(prediction)
    checks.append(not any(n in out for n in HALLUCINATED_NAMES))
    checks.append(EM_DASH not in out)
    return sum(checks) / len(checks)


METRICS = {
    "meddpicc": meddpicc_metric,
    "slack": slack_metric,
    "json": json_metric,
    "brand": brand_metric,
    "isolation": isolation_metric,
}


# ============================================================================
# 3. Training data (from promptfoo fixtures)
# ============================================================================
def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text().strip()


def _load_schema(name: str) -> dict | None:
    p = FIXTURES_DIR / name
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    return data.get("schema", data)


def load_training_data() -> dict[str, list[dspy.Example]]:
    """Load dspy.Example objects for each task from the promptfoo fixtures."""
    data: dict[str, list[dspy.Example]] = {}

    # MEDDPICC: transcript -> output
    data["meddpicc"] = [
        dspy.Example(transcript=_read_fixture("meddpicc-call-transcript-1.txt")).with_inputs("transcript"),
        dspy.Example(transcript=_read_fixture("meddpicc-call-transcript-2.txt")).with_inputs("transcript"),
    ]

    # Slack: task -> output
    data["slack"] = [
        dspy.Example(task=_read_fixture("slack-update-input-1.txt")).with_inputs("task"),
        dspy.Example(task=_read_fixture("slack-update-input-2.txt")).with_inputs("task"),
    ]

    # JSON: task -> output, with schema attached
    data["json"] = [
        dspy.Example(
            task=_read_fixture("json-hubspot-input-1.txt"),
            schema=_load_schema("hubspot-note-schema.json"),
        ).with_inputs("task"),
        dspy.Example(
            task=_read_fixture("json-linear-input-1.txt"),
            schema=_load_schema("linear-ticket-schema.json"),
        ).with_inputs("task"),
    ]

    # Brand: task -> output
    data["brand"] = [
        dspy.Example(task=_read_fixture("brand-email-input-1.txt")).with_inputs("task"),
        dspy.Example(task=_read_fixture("brand-email-input-2.txt")).with_inputs("task"),
    ]

    # Isolation: task -> output
    data["isolation"] = [
        dspy.Example(task=_read_fixture("isolation-input-1.txt")).with_inputs("task"),
        dspy.Example(task=_read_fixture("isolation-input-2.txt")).with_inputs("task"),
    ]

    return data


# ============================================================================
# 4. GEPA optimization runner
# ============================================================================
def _example_to_gepa_data(example: dspy.Example) -> dict:
    """Convert a dspy.Example to a GEPA DefaultDataInst dict."""
    return {
        "input": example.transcript if hasattr(example, "transcript") else example.task,
        "additional_context": {"schema": getattr(example, "schema", None)},
        "answer": "",
    }


def _make_gepa_evaluator(metric_fn):
    """Wrap a (example, prediction, trace) metric into a GEPA Evaluator.

    GEPA's DefaultAdapter calls evaluator(data, response) -> EvaluationResult.
    We reconstruct a lightweight example-like object from the data dict so the
    metric functions keep their specified signature.
    """
    from gepa.adapters.default_adapter.default_adapter import EvaluationResult

    class _Ex:
        def __init__(self, data):
            self.transcript = data.get("input", "")
            self.task = data.get("input", "")
            self.schema = data.get("additional_context", {}).get("schema")

    def evaluator(data, response):
        ex = _Ex(data)
        score = metric_fn(ex, response, None)
        # Build feedback describing which checks failed (helps GEPA reflection)
        feedback = _build_feedback(metric_fn, ex, response, score)
        return EvaluationResult(score=score, feedback=feedback)

    return evaluator


def _build_feedback(metric_fn, ex, response, score) -> str:
    """Generate human-readable feedback for GEPA reflection."""
    if score >= 1.0:
        return "The response is fully correct and passes all checks."
    out = response if isinstance(response, str) else str(response)
    issues = []
    if EM_DASH in out:
        issues.append("contains an em dash (U+2014), which is banned")
    if metric_fn in (brand_metric, isolation_metric):
        low = out.lower()
        found = [p for p in BANNED_PHRASES if p in low]
        if found:
            issues.append(f"contains banned phrase(s): {', '.join(found)}")
    if metric_fn is slack_metric:
        if "|" in out:
            issues.append("contains pipe-table characters (|), which Slack does not render")
        if re.search(r"<[a-zA-Z/][^>]*>", out):
            issues.append("contains HTML tags")
    if metric_fn is meddpicc_metric:
        obj = _parse_json(out)
        if obj is None or not isinstance(obj, dict):
            issues.append("output is not valid JSON with the required 8 MEDDPICC keys")
        else:
            missing = [k for k in MEDDPICC_KEYS if k not in obj]
            if missing:
                issues.append(f"missing MEDDPICC keys: {', '.join(missing)}")
        if any(n in out for n in HALLUCINATED_NAMES):
            issues.append("invented a customer name not present in the transcript")
    if metric_fn is json_metric:
        obj = _parse_json(out)
        if obj is None:
            issues.append("output is not valid JSON")
        elif getattr(ex, "schema", None) and isinstance(obj, dict):
            missing = [k for k in ex.schema.get("required", []) if k not in obj]
            if missing:
                issues.append(f"JSON missing required schema keys: {', '.join(missing)}")
    if metric_fn is isolation_metric:
        if any(n in out for n in HALLUCINATED_NAMES):
            issues.append("mentioned another customer name, violating isolation")
    if not issues:
        issues.append("response did not fully satisfy the task rules")
    return "The response " + "; ".join(issues) + "."


def _baseline_prompt(task_name: str) -> str:
    """Return the baseline system prompt for a task (from the DSPy signature docstring)."""
    sig_map = {
        "meddpicc": MEDDPICCSignature,
        "slack": SlackSignature,
        "json": JSONSignature,
        "brand": BrandSignature,
        "isolation": IsolationSignature,
    }
    return sig_map[task_name].__doc__.strip()


def _score_prompt(task_name: str, prompt: str, examples: list[dspy.Example]) -> float:
    """Score a system prompt on the training examples using the task metric."""
    metric_fn = METRICS[task_name]
    from gepa.adapters.default_adapter.default_adapter import DefaultAdapter
    from gepa.lm import LM

    adapter = DefaultAdapter(
        model=LM(
            GEN_MODEL,
            api_base=COMPANY_BASE,
            api_key=COMPANY_API_KEY,
            max_tokens=8000,
            temperature=0.2,
        ),
        evaluator=_make_gepa_evaluator(metric_fn),
    )
    batch = [_example_to_gepa_data(ex) for ex in examples]
    result = adapter.evaluate(batch, {"system_prompt": prompt}, capture_traces=False)
    return sum(result.scores) / len(result.scores) if result.scores else 0.0


def optimize_task(task_name: str, examples: list[dspy.Example], max_metric_calls: int = 60) -> dict:
    """Run GEPA optimization for a single task. Returns a summary dict."""
    from gepa.adapters.default_adapter.default_adapter import DefaultAdapter
    from gepa.api import optimize
    from gepa.lm import LM
    from gepa.utils import MaxMetricCallsStopper, NoImprovementStopper

    metric_fn = METRICS[task_name]
    seed_prompt = _baseline_prompt(task_name)
    trainset = [_example_to_gepa_data(ex) for ex in examples]

    # Baseline score (before optimization)
    baseline_score = _score_prompt(task_name, seed_prompt, examples)

    task_lm = LM(
        GEN_MODEL,
        api_base=COMPANY_BASE,
        api_key=COMPANY_API_KEY,
        max_tokens=8000,
        temperature=0.2,
    )
    reflection_lm = LM(
        REFLECT_MODEL,
        api_base=COMPANY_BASE,
        api_key=COMPANY_API_KEY,
        max_tokens=1200,
        temperature=0.0,
    )

    run_dir = LOGS_DIR / task_name
    run_dir.mkdir(parents=True, exist_ok=True)

    result = optimize(
        seed_candidate={"system_prompt": seed_prompt},
        trainset=trainset,
        task_lm=task_lm,
        evaluator=_make_gepa_evaluator(metric_fn),
        reflection_lm=reflection_lm,
        max_metric_calls=max_metric_calls,
        stop_callbacks=[NoImprovementStopper(max_iterations_without_improvement=6)],
        run_dir=str(run_dir),
        display_progress_bar=False,
        seed=0,
    )

    best_prompt = result.best_candidate
    if isinstance(best_prompt, dict):
        best_prompt = best_prompt.get("system_prompt", seed_prompt)
    optimized_score = result.val_aggregate_scores[result.best_idx]

    # Save optimized program (prompt) to JSON
    save_path = OPTIMIZED_DIR / f"{task_name}.json"
    payload = {
        "task": task_name,
        "baseline_score": baseline_score,
        "optimized_score": optimized_score,
        "total_metric_calls": result.total_metric_calls,
        "num_candidates": result.num_candidates,
        "best_prompt": best_prompt,
    }
    save_path.write_text(json.dumps(payload, indent=2))
    print(f"  saved -> {save_path}")

    return {
        "task": task_name,
        "baseline_score": baseline_score,
        "optimized_score": optimized_score,
        "total_metric_calls": result.total_metric_calls,
        "num_candidates": result.num_candidates,
    }


def main() -> None:
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(OPTIMIZED_DIR, exist_ok=True)

    modules = build_modules()
    training = load_training_data()

    print("=" * 70)
    print("DSPy + GEPA prompt optimization for the GTM agent eval stack")
    print(f"Generator LM: {GEN_MODEL} | Reflection LM: {REFLECT_MODEL}")
    print("=" * 70)

    summary = []
    for task_name in ["meddpicc", "slack", "json", "brand", "isolation"]:
        examples = training[task_name]
        print(f"\n--- Optimizing: {task_name} ({len(examples)} examples) ---")
        try:
            res = optimize_task(task_name, examples)
            summary.append(res)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR optimizing {task_name}: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'task':<12}{'baseline':<12}{'optimized':<12}{'delta':<10}{'metric_calls'}")
    for r in summary:
        delta = r["optimized_score"] - r["baseline_score"]
        print(
            f"{r['task']:<12}{r['baseline_score']:<12.3f}{r['optimized_score']:<12.3f}"
            f"{delta:<+10.3f}{r['total_metric_calls']}"
        )

    total_calls = sum(r.get("total_metric_calls") or 0 for r in summary)
    print(f"\nTotal metric calls: {total_calls}")


if __name__ == "__main__":
    main()
