#!/usr/bin/env python3
"""
TypeSafe AI (Jev) / Cloudflare Clef client for the GTM engine.
Provides structured ICP scoring, reply classification, signal scoring,
and account analysis using System One primitives.

Everything product-specific (what you sell, who buys it, pain points,
industries, signal types) lives in a product profile YAML, so the same
engine scores accounts for any product. Point GTM_PRODUCT_PROFILE at your
profile; see product_profile.example.yaml.

All results are designed to persist into the account-knowledge store.

Backend selection (TYPESAFE_BACKEND env or the GTM env file):
  jev    - TypeSafe AI only (default)
  clef   - Cloudflare Clef only (Workers AI)
  shadow - Jev primary + Clef shadow; Clef never affects returned results,
           agreement logged to output/clef-shadow.jsonl for cutover gate.

Config file: GTM_ENV_FILE (default ~/.gtm/.env).
"""

import os
import json
import time
import logging
from typing import Optional
from types import SimpleNamespace

import requests

try:  # TypeSafe SDK is only needed for the jev backend
    from typesafe_sdk import TypeSafeClient, Noul, Choice, Score
except ImportError:  # clef backend: same question shapes, no SDK
    TypeSafeClient = None

    class _Question:
        type = ""

        def __init__(self, instructions=None, criteria=None):
            self.type = type(self).type
            self.instructions = instructions
            self.criteria = criteria

    class Noul(_Question):
        type = "noul"

    class Choice(_Question):
        type = "choice"

    class Score(_Question):
        type = "score"

log = logging.getLogger("typesafe_client")

# ── Client singleton ─────────────────────────────────────────────────────────

_client = None

SHADOW_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "output", "clef-shadow.jsonl"
)


def _env_or_file(name: str) -> Optional[str]:
    """Read a config value from the environment, falling back to the GTM env file."""
    val = os.environ.get(name)
    if val:
        return val
    env_path = os.path.expanduser(os.environ.get("GTM_ENV_FILE", "~/.gtm/.env"))
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith(f"{name}="):
                    return line.strip().split("=", 1)[1]
    return None


# ── Cloudflare Clef backend ──────────────────────────────────────────────────

CLEF_API_BASE = "https://api.cloudflare.com/client/v4/accounts"


class ClefClient:
    """Drop-in replacement for TypeSafeClient backed by Cloudflare Clef.

    Exposes the same system_one(state=, questions=) interface and returns
    answer objects with the same attributes (.choice/.score/.noul,
    .confidence, .probabilities, .legend) plus .usage.
    """

    def __init__(self, account_id: str, auth_token: str, model: str = "clef",
                 timeout: float = 90.0):
        self.account_id = account_id
        self.auth_token = auth_token
        self.model = model
        self.timeout = timeout

    def system_one(self, state, questions, model=None, **kwargs):
        q_payload = {}
        for name, q in questions.items():
            d = q.__dict__ if hasattr(q, "__dict__") else dict(q)
            qd = {
                k: v
                for k, v in d.items()
                if k in ("type", "instructions", "criteria") and v is not None
            }
            q_payload[name] = qd

        use_model = model or self.model
        url_model = (
            "@cf/cloudflare/clef-flash" if use_model == "clef-flash"
            else "@cf/cloudflare/clef"
        )
        body = {"model": use_model, "state": state, "questions": q_payload}
        resp = requests.post(
            f"{CLEF_API_BASE}/{self.account_id}/ai/run/{url_model}",
            headers={
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"Clef API error: {data.get('errors')}")
        result = data["result"]
        answers = {
            name: SimpleNamespace(**ans)
            for name, ans in result["answers"].items()
        }
        usage = SimpleNamespace(
            **result.get("usage", {"input_tokens": 0, "output_tokens": 0})
        )
        return SimpleNamespace(
            answers=answers, usage=usage, model=result.get("model", use_model)
        )


def _build_clef_client() -> ClefClient:
    account_id = _env_or_file("CLOUDFLARE_ACCOUNT_ID")
    auth_token = _env_or_file("CLOUDFLARE_AUTH_TOKEN")
    model = _env_or_file("CLEF_MODEL") or "clef"
    if not account_id or not auth_token:
        raise RuntimeError(
            "CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_AUTH_TOKEN not found "
            "in env or GTM_ENV_FILE"
        )
    return ClefClient(account_id, auth_token, model=model)


def _build_jev_client():
    if TypeSafeClient is None:
        raise RuntimeError("TYPESAFE_BACKEND=jev needs the typesafe_sdk package; use clef or install it")
    api_key = _env_or_file("TYPESAFE_API_KEY")
    if not api_key:
        raise RuntimeError("TYPESAFE_API_KEY not found in env or GTM_ENV_FILE")
    os.environ["TYPESAFE_API_KEY"] = api_key
    return TypeSafeClient()


# ── Shadow mode: Jev primary, Clef compared alongside ────────────────────────

def _compare_answers(primary_resp, shadow_resp) -> dict:
    """Per-question comparison between Jev and Clef answers."""
    comparison = {}
    for name, p_ans in primary_resp.answers.items():
        s_ans = shadow_resp.answers.get(name)
        if s_ans is None:
            comparison[name] = {"missing_in_shadow": True}
            continue
        entry = {}
        if hasattr(p_ans, "choice"):
            s_choice = getattr(s_ans, "choice", None)
            entry = {
                "type": "choice",
                "primary": p_ans.choice,
                "shadow": s_choice,
                "agree": p_ans.choice == s_choice,
                "confidence_delta": round(
                    abs((p_ans.confidence or 0)
                        - (getattr(s_ans, "confidence", 0) or 0)), 4
                ),
            }
        elif hasattr(p_ans, "score"):
            s_score = getattr(s_ans, "score", p_ans.score)
            entry = {
                "type": "score",
                "primary": p_ans.score,
                "shadow": s_score,
                "delta": round(abs(p_ans.score - s_score), 4),
            }
        elif hasattr(p_ans, "noul"):
            s_noul = getattr(s_ans, "noul", p_ans.noul)
            entry = {
                "type": "noul",
                "primary": p_ans.noul,
                "shadow": s_noul,
                "delta": round(abs(p_ans.noul - s_noul), 4),
            }
        comparison[name] = entry
    return comparison


class _ShadowClient:
    """Runs Jev as primary and Clef in shadow; logs agreement, returns Jev."""

    def __init__(self, primary, shadow):
        self.primary = primary
        self.shadow = shadow

    def system_one(self, state, questions, **kwargs):
        t0 = time.time()
        primary_resp = self.primary.system_one(
            state=state, questions=questions, **kwargs
        )
        primary_ms = round((time.time() - t0) * 1000)

        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "primary_ms": primary_ms,
            "questions": list(questions.keys()),
        }
        t1 = time.time()
        try:
            shadow_resp = self.shadow.system_one(
                state=state, questions=questions, **kwargs
            )
            entry["ok"] = True
            entry["shadow_ms"] = round((time.time() - t1) * 1000)
            entry["shadow_input_tokens"] = shadow_resp.usage.input_tokens
            entry["comparison"] = _compare_answers(primary_resp, shadow_resp)
        except Exception as e:  # shadow failures must never break the pipeline
            entry["ok"] = False
            entry["error"] = str(e)
            log.warning(f"Clef shadow call failed (non-fatal): {e}")

        try:
            os.makedirs(os.path.dirname(SHADOW_LOG), exist_ok=True)
            with open(SHADOW_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            log.warning(f"Could not write shadow log: {e}")

        return primary_resp


def get_client():
    global _client
    if _client is not None:
        return _client
    backend = (_env_or_file("TYPESAFE_BACKEND") or "jev").lower()
    if backend == "jev":
        _client = _build_jev_client()
    elif backend == "clef":
        _client = _build_clef_client()
    elif backend == "shadow":
        _client = _ShadowClient(_build_jev_client(), _build_clef_client())
        log.info("TYPESAFE_BACKEND=shadow: Jev primary, Clef shadow-logging")
    else:
        raise RuntimeError(f"Unknown TYPESAFE_BACKEND: {backend}")
    return _client



# ── Product profile ──────────────────────────────────────────────────────────
#
# Every prompt below is built from the product profile. Nothing about a
# specific product, market or customer is hardcoded in this file.

_profile = None


def load_profile(path: Optional[str] = None) -> dict:
    """Load the product profile YAML (GTM_PRODUCT_PROFILE or the example)."""
    global _profile
    if _profile is not None and path is None:
        return _profile
    import yaml

    path = path or _env_or_file("GTM_PRODUCT_PROFILE") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "product_profile.example.yaml"
    )
    with open(os.path.expanduser(path)) as f:
        prof = yaml.safe_load(f)
    required = [
        "product_name", "product_summary", "ideal_customer", "need",
        "icp_criteria", "pain_points", "industries", "company_sizes",
        "fit_signals", "signal_types", "current_approach_options",
    ]
    missing = [k for k in required if k not in prof]
    if missing:
        raise ValueError(f"Product profile {path} is missing: {', '.join(missing)}")
    if len(prof["icp_criteria"]) != 5:
        raise ValueError("icp_criteria needs exactly 5 levels (poor to perfect)")
    if len(prof["fit_signals"]) != 2:
        raise ValueError("fit_signals needs exactly 2 entries")
    _profile = prof
    return prof


COMPANY_SIZE_DEFAULT = {
    "startup": "Under 100 employees",
    "smb": "100-500 employees",
    "mid_market": "500-2000 employees",
    "enterprise": "2000-10000 employees",
    "large_enterprise": "10000+ employees",
}


# ── ICP Scoring ──────────────────────────────────────────────────────────────

def score_icp_fit(
    company_name: str,
    domain: str,
    scraped_intel: str,
    industry: str = "",
    employee_count: str = "",
    signals: str = "",
) -> dict:
    """
    Score a company's ICP fit using Jev.
    Returns structured results suitable for persisting to account-knowledge store.
    """
    client = get_client()
    p = load_profile()
    fit_a, fit_b = p["fit_signals"]

    state_parts = [f"Company: {company_name} ({domain})"]
    if industry:
        state_parts.append(f"Industry: {industry}")
    if employee_count:
        state_parts.append(f"Employees: {employee_count}")
    if scraped_intel:
        state_parts.append(f"Scraped Intelligence:\n{scraped_intel}")
    if signals:
        state_parts.append(f"Active Signals:\n{signals}")

    state = "\n\n".join(state_parts)

    questions = {
        "icp_score": Score(
            instructions=(
                f"Rate how well {company_name} fits the ideal customer profile for "
                f"{p['product_name']}: {p['product_summary'].strip()} "
                f"Ideal customers: {p['ideal_customer'].strip()}"
            ),
            criteria=p["icp_criteria"],
        ),
        "buying_intent": Noul(
            instructions=(
                f"Based on the available intelligence, does {company_name} show "
                f"signals of actively evaluating or needing {p['need']}? "
                f"Consider: {p.get('intent_evidence', 'job postings, leadership changes, funding, public initiatives, competitive pressure')}."
            ),
        ),
        "pain_point": Choice(
            instructions=(
                f"Which pain point is most relevant for {company_name} based on "
                "the available intelligence? Pick the ONE that would resonate most "
                "in an outbound sales conversation."
            ),
            criteria=p["pain_points"],
        ),
        "industry_fit": Choice(
            instructions=f"What industry best describes {company_name}?",
            criteria=p["industries"],
        ),
        "company_size": Choice(
            instructions=f"What is the approximate size of {company_name}?",
            criteria=p.get("company_sizes") or COMPANY_SIZE_DEFAULT,
        ),
        "fit_signal_a": Noul(
            instructions=f"{fit_a['question'].strip().format(company=company_name)}",
        ),
        "fit_signal_b": Noul(
            instructions=f"{fit_b['question'].strip().format(company=company_name)}",
        ),
        "urgency_score": Score(
            instructions=(
                f"How urgent is {company_name}'s likely need for {p['need']}? "
                "Consider: active initiatives, deadlines, competitive pressure, "
                "recent changes that create a window."
            ),
            criteria=[
                "No urgency - no visible pressure or timeline",
                "Low urgency - general awareness but no active drivers",
                "Moderate urgency - some pressure building, exploring options",
                "High urgency - active evaluation or imminent deadline",
                "Critical urgency - acute event forcing a decision now",
            ],
        ),
    }

    resp = client.system_one(state=state, questions=questions)

    result = {
        "company": company_name,
        "domain": domain,
        "icp_score": round(resp.answers["icp_score"].score, 2),
        "icp_confidence": round(resp.answers["icp_score"].confidence, 3),
        "icp_probabilities": resp.answers["icp_score"].probabilities,
        "buying_intent": round(resp.answers["buying_intent"].noul, 3),
        "pain_point": resp.answers["pain_point"].choice,
        "pain_point_confidence": round(resp.answers["pain_point"].confidence, 3),
        "pain_point_probabilities": resp.answers["pain_point"].probabilities,
        "industry_fit": resp.answers["industry_fit"].choice,
        "industry_fit_confidence": round(resp.answers["industry_fit"].confidence, 3),
        "company_size": resp.answers["company_size"].choice,
        "company_size_confidence": round(resp.answers["company_size"].confidence, 3),
        fit_a["key"]: round(resp.answers["fit_signal_a"].noul, 3),
        fit_b["key"]: round(resp.answers["fit_signal_b"].noul, 3),
        "urgency_score": round(resp.answers["urgency_score"].score, 2),
        "urgency_confidence": round(resp.answers["urgency_score"].confidence, 3),
        "usage": {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        },
        "scored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Composite priority score (weights adjustable in the profile)
    w = {"icp": 0.35, "intent": 0.20, "fit_a": 0.15, "fit_b": 0.15, "urgency": 0.15}
    w.update(p.get("priority_weights") or {})
    result["composite_priority"] = round(
        (result["icp_score"] / 4.0) * w["icp"]
        + result["buying_intent"] * w["intent"]
        + result[fit_a["key"]] * w["fit_a"]
        + result[fit_b["key"]] * w["fit_b"]
        + (result["urgency_score"] / 4.0) * w["urgency"],
        3,
    )

    # Routing decision
    if result["composite_priority"] >= 0.7 and result["icp_confidence"] >= 0.7:
        result["routing"] = "priority_outbound"
    elif result["composite_priority"] >= 0.5:
        result["routing"] = "standard_outbound"
    elif result["composite_priority"] >= 0.3:
        result["routing"] = "nurture"
    else:
        result["routing"] = "disqualify"

    # Flag for human review if confidence is low
    result["needs_review"] = (
        result["icp_confidence"] < 0.6 or result["pain_point_confidence"] < 0.5
    )

    return result

# ── Reply Classification ─────────────────────────────────────────────────────

REPLY_CATEGORY_OPTIONS = {
    "interested": "Expresses interest, wants to learn more, asks for meeting or demo",
    "not_now": "Not interested right now but leaves the door open for future",
    "wrong_person": "Says they are not the right contact, may or may not redirect",
    "objection_pricing": "Raises pricing or budget concerns",
    "objection_timing": "Raises timing concerns, too busy, competing priorities",
    "objection_competitor": "Mentions using or evaluating a competitor",
    "objection_need": "Questions whether they need this type of solution",
    "unsubscribe": "Asks to be removed from communications",
    "out_of_office": "Automated out-of-office or vacation response",
    "referral": "Refers to another person in the organization",
    "hostile": "Negative, hostile, or threatening response",
    "other": "Does not clearly fit any of the above categories",
}


def classify_reply(
    reply_text: str,
    original_subject: str = "",
    original_body: str = "",
    sender_name: str = "",
    sender_company: str = "",
) -> dict:
    """
    Classify an outbound reply using Jev.
    Returns structured classification for routing and analytics.
    """
    client = get_client()

    state_parts = []
    if original_subject:
        state_parts.append(f"Original Email Subject: {original_subject}")
    if original_body:
        state_parts.append(f"Original Email Body:\n{original_body[:2000]}")
    if sender_name:
        state_parts.append(f"Reply From: {sender_name}")
    if sender_company:
        state_parts.append(f"Company: {sender_company}")
    state_parts.append(f"Reply Text:\n{reply_text}")

    state = "\n\n".join(state_parts)

    questions = {
        "category": Choice(
            instructions="Classify this reply to a cold outbound sales email.",
            criteria=REPLY_CATEGORY_OPTIONS,
        ),
        "buying_intent": Score(
            instructions="Rate the buying intent expressed in this reply.",
            criteria=[
                "No intent - clear rejection or unsubscribe",
                "Low intent - polite brush-off, no engagement",
                "Moderate intent - asks questions, acknowledges problem but non-committal",
                "High intent - expresses interest, wants to learn more",
                "Very high intent - asks for meeting, demo, pricing, or next steps",
            ],
        ),
        "is_positive": Noul(
            instructions="Is this a positive reply that warrants immediate follow-up by a sales rep?",
        ),
        "is_unsubscribe": Noul(
            instructions="Is this person asking to be removed from future communications?",
        ),
        "should_escalate": Noul(
            instructions="Should this reply be escalated to a human sales rep for immediate personal follow-up?",
        ),
        "sentiment": Score(
            instructions="Rate the emotional tone of this reply.",
            criteria=[
                "Hostile or angry",
                "Dismissive or annoyed",
                "Neutral or professional",
                "Friendly or positive",
                "Enthusiastic or excited",
            ],
        ),
    }

    resp = client.system_one(state=state, questions=questions)

    result = {
        "category": resp.answers["category"].choice,
        "category_confidence": round(resp.answers["category"].confidence, 3),
        "category_probabilities": resp.answers["category"].probabilities,
        "buying_intent_score": round(resp.answers["buying_intent"].score, 2),
        "buying_intent_confidence": round(resp.answers["buying_intent"].confidence, 3),
        "is_positive": round(resp.answers["is_positive"].noul, 3),
        "is_unsubscribe": round(resp.answers["is_unsubscribe"].noul, 3),
        "should_escalate": round(resp.answers["should_escalate"].noul, 3),
        "sentiment_score": round(resp.answers["sentiment"].score, 2),
        "sentiment_confidence": round(resp.answers["sentiment"].confidence, 3),
        "usage": {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        },
        "classified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Auto-routing
    if result["is_unsubscribe"] >= 0.8:
        result["action"] = "suppress"
    elif result["should_escalate"] >= 0.7:
        result["action"] = "escalate_to_rep"
    elif result["is_positive"] >= 0.7:
        result["action"] = "notify_rep"
    elif result["category"] == "out_of_office":
        result["action"] = "defer"
    elif result["category"] in ("unsubscribe", "hostile"):
        result["action"] = "suppress"
    else:
        result["action"] = "log_only"

    result["needs_review"] = result["category_confidence"] < 0.6

    return result



# ── Signal Scoring ───────────────────────────────────────────────────────────

def score_signal(
    signal_text: str,
    company_name: str,
    signal_source: str = "",
    existing_context: str = "",
) -> dict:
    """
    Score a raw signal for relevance and actionability.
    Feeds into the signal scanner pipeline.
    """
    client = get_client()
    p = load_profile()

    state_parts = [f"Company: {company_name}"]
    if signal_source:
        state_parts.append(f"Signal Source: {signal_source}")
    state_parts.append(f"Signal:\n{signal_text}")
    if existing_context:
        state_parts.append(f"Existing Account Context:\n{existing_context}")

    state = "\n\n".join(state_parts)

    questions = {
        "signal_type": Choice(
            instructions=f"Classify this signal for {company_name}.",
            criteria=p["signal_types"],
        ),
        "relevance_score": Score(
            instructions=(
                f"How relevant is this signal for selling {p['need']} "
                f"to {company_name}? Does it indicate a potential need or opening?"
            ),
            criteria=[
                f"Not relevant - no connection to {p['need']}",
                "Slightly relevant - tangential connection, weak signal",
                "Moderately relevant - suggests potential need but not urgent",
                "Highly relevant - clear indicator of need",
                "Extremely relevant - direct evidence of active evaluation",
            ],
        ),
        "buying_intent": Noul(
            instructions=(
                f"Does this signal suggest {company_name} is actively evaluating "
                f"or about to evaluate {p['need']}?"
            ),
        ),
        "is_actionable": Noul(
            instructions=(
                f"Is this signal actionable for outbound sales outreach to "
                f"{company_name}? Actionable means a rep could reference this "
                "signal in a personalized email or call and it would resonate."
            ),
        ),
        "urgency": Score(
            instructions="How time-sensitive is this signal?",
            criteria=[
                "Not time-sensitive - old news or no urgency",
                "Low urgency - can reference in next scheduled touch",
                "Moderate urgency - should reference within 1-2 weeks",
                "High urgency - should reference within days",
                "Critical urgency - immediate outreach warranted",
            ],
        ),
    }

    resp = client.system_one(state=state, questions=questions)

    result = {
        "signal_type": resp.answers["signal_type"].choice,
        "signal_type_confidence": round(resp.answers["signal_type"].confidence, 3),
        "relevance_score": round(resp.answers["relevance_score"].score, 2),
        "relevance_confidence": round(resp.answers["relevance_score"].confidence, 3),
        "buying_intent": round(resp.answers["buying_intent"].noul, 3),
        "is_actionable": round(resp.answers["is_actionable"].noul, 3),
        "urgency_score": round(resp.answers["urgency"].score, 2),
        "urgency_confidence": round(resp.answers["urgency"].confidence, 3),
        "usage": {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        },
        "scored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Composite signal quality
    result["signal_quality"] = round(
        (result["relevance_score"] / 4.0) * 0.35
        + result["buying_intent"] * 0.25
        + result["is_actionable"] * 0.20
        + (result["urgency_score"] / 4.0) * 0.20,
        3,
    )

    return result


# ── Account Analysis ─────────────────────────────────────────────────────────

def analyze_account(
    company_name: str,
    domain: str,
    scraped_content: str,
    existing_knowledge: str = "",
) -> dict:
    """
    Deep analysis of scraped account content.
    Extracts structured intelligence for the account-knowledge store.
    """
    client = get_client()
    p = load_profile()

    state_parts = [f"Company: {company_name} ({domain})"]
    if existing_knowledge:
        state_parts.append(f"Existing Knowledge:\n{existing_knowledge}")
    state_parts.append(f"Scraped Content:\n{scraped_content}")

    state = "\n\n".join(state_parts)

    questions = {
        "category_maturity": Score(
            instructions=(
                f"Rate how mature {company_name} is in the area {p['product_name']} "
                f"addresses ({p['need']}), based on the available evidence."
            ),
            criteria=[
                "Nothing visible in this area",
                "Exploring - early experiments or manual workarounds",
                "Adopting - some tooling or a dedicated owner",
                "Advanced - mature program with real investment",
                "Leading - this area is a core strength or differentiator",
            ],
        ),
        "has_problem_evidence": Noul(
            instructions=(
                f"Is there evidence that {company_name} has the problem "
                f"{p['product_name']} solves? {p.get('problem_evidence', '')}".strip()
            ),
        ),
        "has_gap": Noul(
            instructions=(
                f"Is there evidence of a gap at {company_name}: the problem exists "
                "but current tools, process or headcount are not handling it well?"
            ),
        ),
        "current_approach": Choice(
            instructions=(
                f"Based on available intelligence, what is {company_name}'s "
                f"likely current approach to {p['need']}?"
            ),
            criteria=p["current_approach_options"],
        ),
        "data_quality": Score(
            instructions="Rate the quality and completeness of the scraped data.",
            criteria=[
                "Very poor - mostly noise or irrelevant content",
                "Poor - some useful data but significant gaps",
                "Adequate - enough data for basic analysis",
                "Good - comprehensive data with clear signals",
                "Excellent - rich, detailed intelligence",
            ],
        ),
        "recommended_angle": Choice(
            instructions=(
                f"Which sales angle would be most effective for initial outreach "
                f"to {company_name}?"
            ),
            criteria=p["pain_points"],
        ),
    }

    resp = client.system_one(state=state, questions=questions)

    result = {
        "company": company_name,
        "domain": domain,
        "category_maturity_score": round(resp.answers["category_maturity"].score, 2),
        "category_maturity_confidence": round(
            resp.answers["category_maturity"].confidence, 3
        ),
        "has_problem_evidence": round(resp.answers["has_problem_evidence"].noul, 3),
        "has_gap": round(resp.answers["has_gap"].noul, 3),
        "current_approach": resp.answers["current_approach"].choice,
        "current_approach_confidence": round(
            resp.answers["current_approach"].confidence, 3
        ),
        "data_quality_score": round(resp.answers["data_quality"].score, 2),
        "data_quality_confidence": round(resp.answers["data_quality"].confidence, 3),
        "recommended_angle": resp.answers["recommended_angle"].choice,
        "recommended_angle_confidence": round(
            resp.answers["recommended_angle"].confidence, 3
        ),
        "usage": {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        },
        "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    return result

# ── Batch Processing ─────────────────────────────────────────────────────────

def batch_score_accounts(accounts: list[dict], delay_ms: int = 200) -> list[dict]:
    """
    Score multiple accounts with rate limiting.
    Each account dict needs: company_name, domain, scraped_intel (optional), etc.
    """
    results = []
    for i, acct in enumerate(accounts):
        try:
            result = score_icp_fit(
                company_name=acct.get("company_name", ""),
                domain=acct.get("domain", ""),
                scraped_intel=acct.get("scraped_intel", ""),
                industry=acct.get("industry", ""),
                employee_count=acct.get("employee_count", ""),
                signals=acct.get("signals", ""),
            )
            results.append(result)
            log.info(
                f"[{i+1}/{len(accounts)}] {acct.get('company_name')}: "
                f"ICP={result['icp_score']}, Priority={result['composite_priority']}, "
                f"Route={result['routing']}"
            )
        except Exception as e:
            log.error(f"[{i+1}/{len(accounts)}] {acct.get('company_name')}: ERROR - {e}")
            results.append({"company": acct.get("company_name"), "error": str(e)})

        if i < len(accounts) - 1:
            time.sleep(delay_ms / 1000.0)

    return results


# ── Persist to Account Knowledge Store ───────────────────────────────────────

ACCOUNT_KNOWLEDGE_DIR = os.path.expanduser(
    os.environ.get("GTM_ACCOUNT_KNOWLEDGE_DIR", "~/.gtm/account-knowledge")
)


def _fit_signal_lines(result: dict) -> str:
    out = []
    for fs in load_profile()["fit_signals"]:
        out.append(f"- **{fs['label']}:** {result.get(fs['key'], 'N/A')}")
    return "\n".join(out) + "\n"


def persist_icp_score(result: dict):
    """Write ICP scoring results into the account-knowledge store."""
    domain = result.get("domain", "").replace(".", "-")
    if not domain:
        return

    filepath = os.path.join(ACCOUNT_KNOWLEDGE_DIR, f"{domain}.md")

    # Read existing file if it exists
    existing = ""
    if os.path.exists(filepath):
        with open(filepath) as f:
            existing = f.read()

    # Build the Jev scoring section
    jev_section = f"""
## Jev ICP Score (typesafe.ai)
- **ICP Score:** {result.get('icp_score', 'N/A')}/4.0 (confidence: {result.get('icp_confidence', 'N/A')})
- **Composite Priority:** {result.get('composite_priority', 'N/A')}
- **Routing:** {result.get('routing', 'N/A')}
- **Buying Intent:** {result.get('buying_intent', 'N/A')}
- **Pain Point:** {result.get('pain_point', 'N/A')} (confidence: {result.get('pain_point_confidence', 'N/A')})
- **Industry Fit:** {result.get('industry_fit', 'N/A')}
- **Company Size:** {result.get('company_size', 'N/A')}
{_fit_signal_lines(result)}- **Urgency:** {result.get('urgency_score', 'N/A')}/4.0
- **Needs Review:** {result.get('needs_review', 'N/A')}
- **Scored At:** {result.get('scored_at', 'N/A')}
"""

    if "## Jev ICP Score" in existing:
        # Replace existing section
        lines = existing.split("\n")
        new_lines = []
        skip = False
        for line in lines:
            if line.startswith("## Jev ICP Score"):
                skip = True
                new_lines.append(jev_section.strip())
            elif skip and line.startswith("## "):
                skip = False
                new_lines.append(line)
            elif not skip:
                new_lines.append(line)
        content = "\n".join(new_lines)
    else:
        # Append to existing
        if existing and not existing.endswith("\n"):
            existing += "\n"
        content = existing + jev_section

    # Ensure directory exists
    os.makedirs(ACCOUNT_KNOWLEDGE_DIR, exist_ok=True)

    with open(filepath, "w") as f:
        f.write(content)

    log.info(f"Persisted ICP score to {filepath}")


def persist_signal_score(result: dict, company_domain: str):
    """Write signal scoring results into the account-knowledge store."""
    domain = company_domain.replace(".", "-")
    filepath = os.path.join(ACCOUNT_KNOWLEDGE_DIR, f"{domain}.md")

    existing = ""
    if os.path.exists(filepath):
        with open(filepath) as f:
            existing = f.read()

    signal_entry = (
        f"\n### Signal: {result.get('signal_type', 'unknown')} "
        f"(scored {result.get('scored_at', 'N/A')})\n"
        f"- Relevance: {result.get('relevance_score', 'N/A')}/4.0\n"
        f"- Buying Intent: {result.get('buying_intent', 'N/A')}\n"
        f"- Actionable: {result.get('is_actionable', 'N/A')}\n"
        f"- Urgency: {result.get('urgency_score', 'N/A')}/4.0\n"
        f"- Signal Quality: {result.get('signal_quality', 'N/A')}\n"
    )

    if "## Signal Log" in existing:
        content = existing.replace("## Signal Log", "## Signal Log" + signal_entry)
    else:
        content = existing + f"\n## Signal Log{signal_entry}"

    os.makedirs(ACCOUNT_KNOWLEDGE_DIR, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)

    log.info(f"Persisted signal score to {filepath}")


def persist_account_analysis(result: dict):
    """Write account analysis results into the account-knowledge store."""
    domain = result.get("domain", "").replace(".", "-")
    if not domain:
        return

    filepath = os.path.join(ACCOUNT_KNOWLEDGE_DIR, f"{domain}.md")

    existing = ""
    if os.path.exists(filepath):
        with open(filepath) as f:
            existing = f.read()

    analysis_section = f"""
## Jev Account Analysis (typesafe.ai)
- **Category Maturity:** {result.get('category_maturity_score', 'N/A')}/4.0 (confidence: {result.get('category_maturity_confidence', 'N/A')})
- **Problem Evidence:** {result.get('has_problem_evidence', 'N/A')}
- **Gap:** {result.get('has_gap', 'N/A')}
- **Current Approach:** {result.get('current_approach', 'N/A')}
- **Data Quality:** {result.get('data_quality_score', 'N/A')}/4.0
- **Recommended Angle:** {result.get('recommended_angle', 'N/A')} (confidence: {result.get('recommended_angle_confidence', 'N/A')})
- **Analyzed At:** {result.get('analyzed_at', 'N/A')}
"""

    if "## Jev Account Analysis" in existing:
        lines = existing.split("\n")
        new_lines = []
        skip = False
        for line in lines:
            if line.startswith("## Jev Account Analysis"):
                skip = True
                new_lines.append(analysis_section.strip())
            elif skip and line.startswith("## "):
                skip = False
                new_lines.append(line)
            elif not skip:
                new_lines.append(line)
        content = "\n".join(new_lines)
    else:
        if existing and not existing.endswith("\n"):
            existing += "\n"
        content = existing + analysis_section

    os.makedirs(ACCOUNT_KNOWLEDGE_DIR, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)

    log.info(f"Persisted account analysis to {filepath}")


# ── CLI for testing ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        result = score_icp_fit(
            company_name="Northwind Logistics",
            domain="northwind.example",
            scraped_intel="2,000-person logistics company. Posted 3 operations engineering roles last month. New VP of Operations started in Q3. Announced a modernization program on its last earnings call.",
        )
        print(json.dumps(result, indent=2))
        persist_icp_score(result)
    elif len(sys.argv) > 1 and sys.argv[1] == "test-reply":
        result = classify_reply(
            reply_text="Thanks for reaching out. We're looking at options for this right now. Can you send pricing and set up a demo for next week?",
            original_subject="Quick question about your Q3 rollout",
            sender_name="Dana Reyes",
            sender_company="Northwind Logistics",
        )
        print(json.dumps(result, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "test-signal":
        result = score_signal(
            signal_text="Northwind Logistics posts a Director of Operations Automation role to lead a company-wide tooling consolidation.",
            company_name="Northwind Logistics",
            signal_source="Job board",
        )
        print(json.dumps(result, indent=2))
    else:
        print("Usage: typesafe_client.py [test|test-reply|test-signal]")
