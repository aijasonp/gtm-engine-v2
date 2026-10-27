#!/usr/bin/env python3
"""signal_decay.py: apply gtm-vault/signals/decay-config.json to one signal. Pure, no network.

Every signal source (competitor engagers, Reddit buyer language, and anything added later) calls
`score_signal()` so freshness, strength and category weight come from the one config the vault
already owns, instead of each script hardcoding its own windows.

score = strength_multiplier * age_multiplier * category_priority_weight
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1] / "gtm-vault" / "signals"
DECAY_CONFIG = VAULT / "decay-config.json"
TAXONOMY = VAULT / "signal-taxonomy.json"


def load_config(path: Path = DECAY_CONFIG) -> dict:
    return json.loads(Path(path).read_text())


def load_taxonomy(path: Path = TAXONOMY) -> dict:
    return json.loads(Path(path).read_text())


def signal_def(signal_id: str, taxonomy: dict) -> tuple[dict, dict]:
    """(category, signal) for a signal_id. Raises KeyError when the id is not in the taxonomy,
    so a typo fails loudly instead of scoring as a default."""
    for cat in taxonomy.get("categories", []):
        for sig in cat.get("signals", []):
            if sig.get("signal_id") == signal_id:
                return cat, sig
    raise KeyError(f"signal_id not in taxonomy: {signal_id}")


def age_days(when: str | datetime | None, now: datetime | None = None) -> int | None:
    if not when:
        return None
    now = now or datetime.now(timezone.utc)
    if isinstance(when, datetime):
        dt = when
    else:
        s = str(when).strip()
        if s.isdigit():
            dt = datetime.fromtimestamp(int(s) / (1000 if len(s) > 11 else 1), tz=timezone.utc)
        else:
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (now - dt).days)


def freshness(age: int | None, decay_days: int, config: dict) -> tuple[str, float]:
    """(label, multiplier). Unknown age is treated as stale, never fresh."""
    sc = config["scoring"]
    if age is None:
        return sc["stale"]["label"], sc["stale"]["score_multiplier"]
    if age > decay_days:
        return sc["expired"]["label"], sc["expired"]["score_multiplier"]
    if age <= sc["fresh"]["threshold_days"]:
        return sc["fresh"]["label"], sc["fresh"]["score_multiplier"]
    if age <= sc["warm"]["threshold_days"]:
        return sc["warm"]["label"], sc["warm"]["score_multiplier"]
    return sc["stale"]["label"], sc["stale"]["score_multiplier"]


def score_signal(signal_id: str, observed_at, strength: str | None = None, config: dict | None = None,
                 taxonomy: dict | None = None, now: datetime | None = None) -> dict:
    """Score one observed signal. `strength` overrides the taxonomy default (high|medium|low)."""
    config = config or load_config()
    taxonomy = taxonomy or load_taxonomy()
    cat, sig = signal_def(signal_id, taxonomy)
    cat_id = cat["category_id"]
    decay_days = int(sig.get("decay_days")
                     or config.get("category_overrides", {}).get(cat_id, {}).get("decay_days")
                     or config.get("default_decay_days", 90))
    strength = (strength or sig.get("strength") or "medium").lower()
    s_mult = config["strength_multipliers"].get(strength, config["strength_multipliers"]["medium"])
    weights = config["composite_score_formula"]["category_priority_weights"]
    c_weight = weights.get(str(cat.get("priority")), min(float(v) for v in weights.values()))
    age = age_days(observed_at, now)
    label, a_mult = freshness(age, decay_days, config)
    return {"signal_id": signal_id, "category_id": cat_id, "strength": strength, "age_days": age,
            "decay_days": decay_days, "freshness": label,
            "score": round(s_mult * a_mult * float(c_weight), 3)}


def account_tier(total: float, config: dict | None = None) -> str:
    th = (config or load_config())["composite_score_formula"]["thresholds"]
    if total >= th["tier1_enterprise"]:
        return "tier1_enterprise"
    if total >= th["tier2_qualified"]:
        return "tier2_qualified"
    if total >= th["tier3_monitor"]:
        return "tier3_monitor"
    return "below_threshold"
