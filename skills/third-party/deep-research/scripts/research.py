#!/usr/bin/env python3
"""
Deep Research Client — stdlib only, no third-party dependencies.

Calls OpenAI's Responses API with background mode for long-running
deep research queries. Polls for completion and outputs a markdown report.

Usage:
    python3 research.py "Your research query" -o report.md -v
    python3 research.py "Query" --model o3-deep-research -o report.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from typing import Optional, Tuple, List, Dict

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "o4-mini-deep-research"
POLL_INTERVAL_S = 5
PROGRESS_LOG_INTERVAL_S = 30
OPENAI_API_BASE = "https://api.openai.com/v1"

SYSTEM_INSTRUCTIONS = (
    "You are a professional research analyst preparing a comprehensive, "
    "structured report.\n\n"
    "Your research should be:\n"
    "- Thorough: Cover all aspects of the topic with depth\n"
    "- Well-sourced: Include inline citations for every major claim\n"
    "- Actionable: Provide specific details, code examples, and step-by-step "
    "guidance where applicable\n"
    "- Structured: Use clear sections with headers\n"
    "- Complete: Include edge cases, limitations, and gotchas\n\n"
    "Format your output as a well-structured markdown report with:\n"
    "1. Executive summary\n"
    "2. Detailed sections covering all aspects\n"
    "3. Code examples where relevant\n"
    "4. A \"Sources\" section at the end listing all referenced URLs"
)


# ---------------------------------------------------------------------------
# API key resolution
# ---------------------------------------------------------------------------

def get_api_key() -> str:
    """Resolve OpenAI API key from env var or OpenClaw config."""
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key

    # Try OpenClaw config
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(config_path) as f:
            cfg = json.load(f)
        key = (
            cfg.get("skills", {})
            .get("entries", {})
            .get("openai-whisper-api", {})
            .get("apiKey")
        )
        if key:
            return key
    except (OSError, json.JSONDecodeError):
        pass

    print("Error: No OpenAI API key found.", file=sys.stderr)
    print("Set OPENAI_API_KEY or configure in OpenClaw config.", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def api_request(method: str, path: str, api_key: str, body: dict | None = None) -> dict:
    """Make an authenticated request to the OpenAI API."""
    url = f"{OPENAI_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"API error {e.code}: {error_body}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Deep Research
# ---------------------------------------------------------------------------

def submit_research(query: str, model: str, api_key: str, verbose: bool) -> str:
    """Submit a deep research request. Returns the response ID."""
    if verbose:
        print(f"[research] Submitting to {model}...", file=sys.stderr)
        print(f"[research] Query: {query[:120]}{'...' if len(query) > 120 else ''}", file=sys.stderr)

    body = {
        "model": model,
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": query,
        "tools": [
            {"type": "web_search_preview"},
        ],
        "reasoning": {"summary": "auto"},
        "background": True,
    }

    resp = api_request("POST", "/responses", api_key, body)
    response_id = resp.get("id")
    if not response_id:
        print(f"Error: No response ID returned: {json.dumps(resp)}", file=sys.stderr)
        sys.exit(1)

    if verbose:
        print(f"[research] Submitted, ID: {response_id}", file=sys.stderr)
        print("[research] Polling for completion (5-30 min)...", file=sys.stderr)

    return response_id


def poll_until_done(response_id: str, api_key: str, verbose: bool) -> dict:
    """Poll the response until completed or failed."""
    start = time.time()
    last_progress = start
    poll_count = 0

    while True:
        time.sleep(POLL_INTERVAL_S)
        poll_count += 1

        result = api_request("GET", f"/responses/{response_id}", api_key)
        status = result.get("status", "unknown")

        now = time.time()
        if verbose and (now - last_progress) >= PROGRESS_LOG_INTERVAL_S:
            elapsed = int(now - start)
            print(f"[research] Still running... ({elapsed}s elapsed, status: {status})", file=sys.stderr)
            last_progress = now

        if status == "completed":
            if verbose:
                elapsed = int(time.time() - start)
                print(f"[research] Completed in {elapsed}s", file=sys.stderr)
            return result

        if status in ("failed", "cancelled", "expired"):
            print(f"Error: Research {status}: {json.dumps(result)}", file=sys.stderr)
            sys.exit(1)


def extract_results(response: dict) -> Tuple[str, List[Dict], Optional[str]]:
    """Extract report text, sources, and reasoning summary from the response."""
    report_parts = []
    sources = []
    reasoning_summary = None

    for item in response.get("output", []):
        # Final message content
        if item.get("type") == "message":
            for content in item.get("content", []):
                text = content.get("text", "")
                if text:
                    report_parts.append(text)

                # Extract citation annotations
                for ann in content.get("annotations", []):
                    url = ann.get("url")
                    if url:
                        sources.append({
                            "title": ann.get("title", url),
                            "url": url,
                        })

        # Reasoning summary
        if item.get("type") == "reasoning":
            summary_items = item.get("summary", [])
            if summary_items:
                parts = []
                for s in summary_items:
                    if isinstance(s, str):
                        parts.append(s)
                    elif isinstance(s, dict):
                        parts.append(s.get("text", ""))
                if parts:
                    reasoning_summary = "\n".join(parts)

    # Deduplicate sources by URL
    seen_urls = set()
    unique_sources = []
    for src in sources:
        if src["url"] not in seen_urls:
            seen_urls.add(src["url"])
            unique_sources.append(src)

    return "\n\n".join(report_parts), unique_sources, reasoning_summary


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_report(
    query: str,
    model: str,
    report: str,
    sources: list[dict],
    reasoning_summary: str | None,
    duration_s: int,
) -> str:
    """Format the research results as a markdown document."""
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    lines = [
        "# Deep Research Report\n",
        f"**Model:** {model}",
        f"**Generated:** {timestamp}",
        f"**Duration:** {duration_s} seconds\n",
        "---\n",
        "## Research Query\n",
        query + "\n",
        "---\n",
        report,
    ]

    if reasoning_summary:
        lines.extend([
            "\n---\n",
            "## Reasoning Summary\n",
            reasoning_summary,
        ])

    if sources:
        lines.extend([
            "\n---\n",
            "## Sources\n",
        ])
        for src in sources:
            lines.append(f"- [{src['title']}]({src['url']})")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OpenAI Deep Research client (stdlib only)")
    parser.add_argument("query", help="Research query")
    parser.add_argument("-o", "--output", help="Save report to file (default: stdout)")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=["o4-mini-deep-research", "o3-deep-research"],
        help=f"Model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Progress to stderr")
    args = parser.parse_args()

    api_key = get_api_key()
    start = time.time()

    response_id = submit_research(args.query, args.model, api_key, args.verbose)
    result = poll_until_done(response_id, api_key, args.verbose)

    report, sources, reasoning = extract_results(result)
    duration_s = int(time.time() - start)

    output = format_report(args.query, args.model, report, sources, reasoning, duration_s)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Report saved to: {os.path.abspath(args.output)}", file=sys.stderr)
    else:
        print(output)

    if args.verbose:
        print(f"[research] {len(sources)} sources cited, {len(report)} chars", file=sys.stderr)


if __name__ == "__main__":
    main()
