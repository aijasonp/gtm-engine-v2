#!/usr/bin/env python3
"""MCP server for the JEV/CLEF scoring engine.

Exposes the four engines in typesafe_client.py as tools so NetClaw agents call
deterministic, structured scoring instead of guessing in a prompt:

    score_account   ICP fit, intent, fit signals, urgency, routing
    score_signal    relevance, intent, actionability, urgency of one signal
    classify_reply  category, intent, sentiment, next action for a reply
    analyze_account category maturity, problem evidence, gap, current approach

Results are also written to the account-knowledge store unless persist=False.

Run:
    python3 scoring_mcp.py                                   # stdio
    python3 scoring_mcp.py --transport streamable-http --host 0.0.0.0 --port 8010

Config: GTM_PRODUCT_PROFILE, TYPESAFE_BACKEND (jev|clef|shadow), backend keys in
env or GTM_ENV_FILE. See product_profile.example.yaml.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import typesafe_client as engine  # noqa: E402


def _server_class():
    try:  # mcp >= 2
        from mcp.server.mcpserver import MCPServer
        return MCPServer
    except ImportError:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP
        return FastMCP


def score_account(company_name: str, domain: str, scraped_intel: str = "", industry: str = "",
                  employee_count: str = "", signals: str = "", persist: bool = True) -> dict:
    """Score one account's ICP fit and buying readiness. Returns icp_score (0-4), composite_priority (0-1), routing (priority_outbound, standard_outbound, nurture, disqualify), pain_point and needs_review."""
    r = engine.score_icp_fit(company_name, domain, scraped_intel, industry, employee_count, signals)
    if persist:
        engine.persist_icp_score(r)
    return r


def score_signal(signal_text: str, company_name: str, company_domain: str = "",
                 signal_source: str = "", existing_context: str = "", persist: bool = True) -> dict:
    """Score one raw buying signal for an account. Returns signal_type, relevance_score (0-4), buying_intent, is_actionable, urgency_score and signal_quality (0-1)."""
    r = engine.score_signal(signal_text, company_name, signal_source, existing_context)
    if persist and company_domain:
        engine.persist_signal_score(r, company_domain)
    return r


def classify_reply(reply_text: str, original_subject: str = "", original_body: str = "",
                   sender_name: str = "", sender_company: str = "") -> dict:
    """Classify a prospect's reply to outbound. Returns category, buying_intent_score, sentiment_score and action (suppress, escalate_to_rep, notify_rep, defer, log_only)."""
    return engine.classify_reply(reply_text, original_subject, original_body, sender_name, sender_company)


def analyze_account(company_name: str, domain: str, scraped_content: str,
                    existing_knowledge: str = "", persist: bool = True) -> dict:
    """Deep analysis of researched account content. Returns category_maturity_score, has_problem_evidence, has_gap, current_approach and recommended_angle."""
    r = engine.analyze_account(company_name, domain, scraped_content, existing_knowledge)
    if persist:
        engine.persist_account_analysis(r)
    return r


TOOLS = [score_account, score_signal, classify_reply, analyze_account]


def main() -> None:
    ap = argparse.ArgumentParser(description="Scoring engine MCP server")
    ap.add_argument("--transport", default="stdio", choices=["stdio", "sse", "streamable-http"])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8010)
    a = ap.parse_args()
    engine.load_profile()  # fail fast on a bad profile
    server = _server_class()("scoring-engine", instructions="Structured account, signal and reply scoring.")
    for fn in TOOLS:
        server.tool(name=fn.__name__, description=fn.__doc__)(fn)
    if a.transport == "stdio":
        server.run(transport="stdio")
        return
    try:
        server.run(transport=a.transport, host=a.host, port=a.port)
    except TypeError:
        server.settings.host, server.settings.port = a.host, a.port
        server.run(transport=a.transport)


if __name__ == "__main__":
    main()
