#!/usr/bin/env python3
"""Interactive sales roleplay coach.

Features:
- CLI-based conversation where the user plays the prospect
- The AI plays the AE (AE_NAME, default "Sam") across 8 predefined stages
- Seller context comes from the product profile (GTM_PRODUCT_PROFILE)
- Stage classification after every AE response (claude-haiku-4-5)
- Coaching feedback summary at the end (claude-sonnet-4-6)

Usage:
    python skills/sales-coach/sales_coach.py --persona economic_buyer
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-6"
CLASSIFIER_MODEL = "claude-haiku-4-5"

STAGES = [
    "Introduction",
    "Qualification",
    "Value proposition",
    "Needs analysis",
    "Solution presentation",
    "Objection handling",
    "Close",
    "End conversation",
]

AE_NAME = os.environ.get("AE_NAME", "Sam")

PERSONAS = {
    "economic_buyer": {
        "title": "Senior executive who owns the budget for this problem",
        "traits": "Skeptical, short on time, wants evidence and a business case before moving",
        "focus": "Business outcome, risk, cost of doing nothing, proof from similar companies",
    },
    "technical_buyer": {
        "title": "Technical leader who will run the product day to day",
        "traits": "Detail-oriented, evaluates build vs buy, worried about integration effort",
        "focus": "Architecture fit, total cost of ownership, time to value",
    },
    "champion": {
        "title": "Mid-level manager who feels the pain daily",
        "traits": "Interested but cautious, needs help selling internally",
        "focus": "Making the case to leadership, quick wins, low personal risk",
    },
    "procurement": {
        "title": "Procurement lead",
        "traits": "Price-driven, gatekeeper mentality, cares about commercial terms",
        "focus": "Budget fit, vendor viability, contract guardrails",
    },
}


def seller_context() -> str:
    """Build the seller context block from the product profile."""
    path = read_env_value("GTM_PRODUCT_PROFILE")
    if not path:
        return "Seller: a B2B software company. No product profile set; keep claims general."
    import yaml

    with open(os.path.expanduser(path), encoding="utf-8") as fh:
        p = yaml.safe_load(fh)
    lines = [
        f"Company/product: {p.get('product_name', '')}: {str(p.get('product_summary', '')).strip()}",
        f"ICP: {str(p.get('ideal_customer', '')).strip()}",
        "Pain points: " + "; ".join((p.get("pain_points") or {}).values()),
        "Differentiators: " + "; ".join(p.get("differentiators") or []),
        "Competitors: " + ", ".join(c.get("name", "") for c in (p.get("competitors") or [])),
        "Verified proof points (use only these): " + "; ".join(p.get("proof_points") or []),
    ]
    return "\n".join(lines)


class AnthropicClient:
    def __init__(self, api_key: str, timeout: int = 60) -> None:
        self.api_key = api_key.strip()
        self.timeout = timeout

    def call(
        self,
        *,
        model: str,
        system_prompt: str,
        messages: List[Dict[str, object]],
        max_tokens: int,
        temperature: float = 0.6,
    ) -> str:
        payload = {
            "model": model,
            "system": system_prompt,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        req = urllib.request.Request(ANTHROPIC_URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                result = json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8") if hasattr(exc, "read") else str(exc)
            raise RuntimeError(f"Anthropic HTTP {getattr(exc, 'code', 'error')}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error: {exc}") from exc

        text_chunks = []
        for block in result.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                text_chunks.append(block.get("text", ""))
        return "".join(text_chunks).strip()


def read_env_value(key: str) -> Optional[str]:
    candidate = os.environ.get(key)
    if candidate:
        return candidate.strip()
    env_path = os.path.expanduser(os.environ.get("GTM_ENV_FILE", "~/.gtm/.env"))
    if not os.path.exists(env_path):
        return None
    with open(env_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() == key:
                return value.strip()
    return None


def load_anthropic_key() -> str:
    key = read_env_value("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY is required (set env var or GTM_ENV_FILE)")
    return key


def format_persona_description(persona_key: str) -> str:
    persona = PERSONAS[persona_key]
    return textwrap.dedent(
        f"""
        Prospect persona: {persona['title']}.
        Traits: {persona['traits']}.
        Primary focus: {persona['focus']}.
        """
    ).strip()


def build_system_prompt() -> str:
    return (
        f"You are {AE_NAME}, a senior Account Executive."
        " Stay grounded, concise, and human."
        " Drive the conversation through each stage, referencing the prospect's pain points"
        " and the differentiators in the seller context. Never invent proof points."
        " Ask thoughtful questions, summarize learning, and set clear next steps."
        " Never break character or mention that you are an AI."
    )


def stage_header(stage_name: str) -> None:
    banner = f"=== Stage: {stage_name} ==="
    print("\n" + banner)


def append_message(history: List[Dict[str, object]], role: str, text: str) -> None:
    history.append({"role": role, "content": [{"type": "text", "text": text}]})


def ae_turn(
    client: AnthropicClient,
    history: List[Dict[str, object]],
    persona_key: str,
    stage_name: str,
    turn_index: int,
) -> str:
    persona_desc = format_persona_description(persona_key)
    guidance = (
        f"Stage: {stage_name}. Respond as {AE_NAME} advancing an enterprise deal.\n"
        f"{persona_desc}\n"
        f"Seller context:\n{seller_context()}\n"
        "Explicitly reference the prospect's latest input, ask one purposeful question,"
        " and recommend next actions tied to the prospect's stated pain."
    )
    append_message(history, "user", guidance)
    response = client.call(
        model=DEFAULT_MODEL,
        system_prompt=build_system_prompt(),
        messages=history,
        max_tokens=600,
        temperature=0.65,
    )
    append_message(history, "assistant", response)
    print(f"\n{AE_NAME}: {response}\n")
    return response


def classify_stage(
    client: AnthropicClient,
    transcript: str,
    fallback_stage: str,
) -> str:
    prompt = textwrap.dedent(
        f"""
        Conversation transcript (latest ~1200 chars):
        {transcript[-1200:]}

        Available stages:
        1. Introduction - warm greeting, establish reason for call
        2. Qualification - confirm authority, MEDDIC discovery
        3. Value proposition - lead differentiator tied to their pain
        4. Needs analysis - open-ended discovery
        5. Solution presentation - tailor to stated pain
        6. Objection handling - handle with proof points
        7. Close - propose next step (demo/POC/exec meeting)
        8. End conversation - mutual wrap-up

        Output strictly as JSON: {"stage_number": <1-8>, "stage_name": "<name>"} indicating the stage that best describes the AE's most recent reply.
        """
    ).strip()
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    try:
        raw = client.call(
            model=CLASSIFIER_MODEL,
            system_prompt="You classify the current conversation stage.",
            messages=messages,
            max_tokens=200,
            temperature=0.1,
        )
        data = json.loads(raw)
        number = int(data.get("stage_number"))
        if 1 <= number <= len(STAGES):
            return STAGES[number - 1]
    except Exception:
        pass
    # fallback to heuristic search
    lower = transcript.lower()
    if "next step" in lower or "follow-up" in lower:
        return "Close"
    return fallback_stage


def build_coaching_feedback(
    client: AnthropicClient,
    stage_history: List[str],
    transcript: str,
    persona_key: str,
) -> str:
    persona_desc = format_persona_description(persona_key)
    stage_chain = " -> ".join(stage_history) if stage_history else "No stages recorded"
    prompt = textwrap.dedent(
        f"""
        You are coaching {AE_NAME} after a simulated sales call.
        Persona: {persona_desc}
        Stage progression: {stage_chain}

        Transcript:
        {transcript}

        Produce a coaching note that includes:
        - Stage progression commentary
        - Discovery quality assessment
        - Objection handling feedback
        - Value alignment check
        - Close quality review
        - Overall score (0-100)
        - Top 3 strengths (bulleted)
        - Top 3 improvements (bulleted)
        - Three suggested alternative phrases {AE_NAME} could have used

        Keep it under 350 words.
        """
    ).strip()
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    return client.call(
        model=DEFAULT_MODEL,
        system_prompt="You are a precise enterprise sales coach.",
        messages=messages,
        max_tokens=700,
        temperature=0.4,
    )


def interactive_session(persona_key: str) -> None:
    api_key = load_anthropic_key()
    client = AnthropicClient(api_key)
    history: List[Dict[str, object]] = []
    transcript_lines: List[str] = []
    stage_history: List[str] = []
    current_stage = STAGES[0]
    turn_index = 0

    print(f"Sales Coaching Tool: {AE_NAME} roleplay")
    print("Type your prospect responses. Enter EXIT or END to finish.\n")

    try:
        while True:
            stage_header(current_stage)
            turn_index += 1
            response = ae_turn(client, history, persona_key, current_stage, turn_index)
            stage_history.append(current_stage)
            transcript_lines.append(f"{AE_NAME} ({current_stage}): {response}")

            # classify stage for next turn
            transcript_text = "\n".join(transcript_lines)
            current_stage = classify_stage(client, transcript_text, current_stage)

            user_input = input("Prospect: ").strip()
            if user_input.upper() in {"EXIT", "END"}:
                print("\nEnding session… generating coaching feedback...\n")
                break
            if not user_input:
                continue
            append_message(
                history,
                "user",
                f"Prospect reply ({current_stage} focus): {user_input}",
            )
            transcript_lines.append(f"Prospect: {user_input}")
    except KeyboardInterrupt:
        print("\nSession interrupted. Generating coaching feedback...\n")

    transcript_text = "\n".join(transcript_lines)
    if not transcript_text:
        print("No conversation captured. Nothing to coach.")
        return

    feedback = build_coaching_feedback(client, stage_history, transcript_text, persona_key)
    print("=== Coaching Feedback ===")
    print(feedback)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sales Coaching Tool")
    parser.add_argument(
        "--persona",
        choices=sorted(PERSONAS.keys()),
        default="economic_buyer",
        help="Prospect persona to simulate",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    interactive_session(args.persona)
    return 0


if __name__ == "__main__":
    sys.exit(main())
