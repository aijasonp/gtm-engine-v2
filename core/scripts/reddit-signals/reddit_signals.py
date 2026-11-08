#!/usr/bin/env python3
"""reddit_signals.py: buyer language from Reddit, classified into vault community-intent signals.

Adapted from the reddit-buyer-signals starter in shawnla90/gtm-coding-agent (MIT; see THIRD_PARTY.md).
The vocabulary lives in a JSON config instead of code, so re-pointing at a new product or a design
partner's market is a config change.

Each thread title, body and comment is checked twice:
  is_relevant  names a tracked vendor or a category noun (keeps careers, gaming and politics out)
  classify     comparison | recommendation | pain | question  -> reddit-vendor-comparison,
               reddit-recommendation-ask, reddit-vendor-pain, reddit-category-question

Input is any export: Clearbox, an Apify Reddit actor dataset, or a CSV. Field names are aliased.

  python3 reddit_signals.py import threads.json --config reddit.json        # load + classify
  python3 reddit_signals.py pull --config reddit.json                       # Apify actor from config
  python3 reddit_signals.py export --config reddit.json --out reddit_signals.csv
  python3 reddit_signals.py export --config reddit.json --vault-language    # phrases -> gtm-vault/language
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "lib"))
import apify_client  # noqa: E402
import signal_decay  # noqa: E402

VAULT_LANGUAGE = HERE.parents[1] / "gtm-vault" / "language" / "community-language.json"

KIND_TO_SIGNAL = {
    "comparison": "reddit-vendor-comparison",
    "recommendation": "reddit-recommendation-ask",
    "pain": "reddit-vendor-pain",
    "question": "reddit-category-question",
}

DEFAULT_PAIN = ["too expensive", "overpriced", "price increase", "bloated", "overkill", "clunky", "confusing",
                "steep learning curve", "frustrat", "regret", "nightmare", "buggy", "locked behind", "paywall",
                "gave up", "switching away", "moving off", "doesn't scale", "does not scale"]
DEFAULT_COMPARE = [" vs ", " vs.", "versus", "compared to", " or "]
DEFAULT_QUESTION = ["which", "what ", "should i", "recommend", "worth it", "advice", "looking for", "best ",
                    "thoughts on", "any good", "opinions", "suggestions", "alternative"]
RECOMMEND_HINTS = ["recommend", "looking for", "which", "best ", "alternative", "replace", "shortlist"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY, thread_id TEXT, kind_src TEXT, subreddit TEXT, author TEXT, text TEXT,
  permalink TEXT, created_at TEXT, score INTEGER, imported_at TEXT);
CREATE TABLE IF NOT EXISTS signals (
  id TEXT PRIMARY KEY, item_id TEXT, kind TEXT, signal_id TEXT, brands TEXT, topics TEXT, quote TEXT,
  subreddit TEXT, author TEXT, permalink TEXT, created_at TEXT, engagement INTEGER, freshness TEXT,
  signal_score REAL);
"""


class Vocabulary:
    """Brands, category nouns and topics for one market. Pure."""

    def __init__(self, cfg: dict):
        self.brands = [b.lower() for b in cfg.get("brands", [])]
        self.canon = {k.lower(): v.lower() for k, v in cfg.get("brand_aliases", {}).items()}
        self.category = [c.lower() for c in cfg.get("category", [])]
        self.topics = {t: [k.lower() for k in ks] for t, ks in cfg.get("topics", {}).items()}
        self.pain = [p.lower() for p in cfg.get("pain", DEFAULT_PAIN)]
        self.compare = cfg.get("compare", DEFAULT_COMPARE)
        self.question = cfg.get("question_hints", DEFAULT_QUESTION)

    @staticmethod
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").lower()).strip()

    def _contains(self, t: str, term: str) -> bool:
        # word-boundary match so short brand names ("hive", "motion") do not fire inside other words
        return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", t) is not None

    def brands_in(self, text: str) -> list[str]:
        t, found = self.norm(text), []
        for b in self.brands + list(self.canon):
            if self._contains(t, b):
                c = self.canon.get(b, b)
                if c not in found:
                    found.append(c)
        return found

    def topics_in(self, text: str) -> list[str]:
        t = self.norm(text)
        return [topic for topic, kws in self.topics.items() if any(k in t for k in kws)]

    def is_relevant(self, text: str) -> bool:
        t = self.norm(text)
        return bool(self.brands_in(t)) or any(self._contains(t, c) for c in self.category)

    def classify(self, text: str) -> str | None:
        t = self.norm(text)
        if any(c in f" {t} " for c in self.compare) and len(self.brands_in(t)) >= 1:
            if len(self.brands_in(t)) >= 2 or "versus" in t or " vs" in t:
                return "comparison"
        if any(p in t for p in self.pain):
            return "pain"
        if t.endswith("?") or any(h in t for h in self.question):
            return "recommendation" if any(h in t for h in RECOMMEND_HINTS) else "question"
        return None


# ----------------------------------------------------------------------------- import (pure normalizers)
def _first(d: dict, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return default


def to_iso(value) -> str:
    if value in (None, ""):
        return ""
    s = str(value).strip()
    try:
        if s.replace(".", "", 1).isdigit():
            v = float(s)
            return datetime.fromtimestamp(v / 1000 if v > 1e12 else v, tz=timezone.utc).isoformat(timespec="seconds")
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, OverflowError, OSError):
        return ""


def explode(record: dict) -> list[dict]:
    """One export record (a thread, with or without nested comments, or a single comment) -> items."""
    perm = _first(record, "permalink", "url", "link", "postUrl")
    if perm and perm.startswith("/"):
        perm = "https://www.reddit.com" + perm
    thread_id = str(_first(record, "thread_id", "parentId", "postId", "id", "external_id", default=perm))
    sub = str(_first(record, "subreddit", "communityName", "parsedCommunityName", "sub")).removeprefix("r/")
    created = to_iso(_first(record, "created_utc", "createdAt", "created_at", "created", "date"))
    score = int(float(_first(record, "score", "upVotes", "ups", "upvotes", default=0) or 0))
    author = str(_first(record, "author", "username", "user"))
    kind_src = "comment" if str(_first(record, "dataType", "type", "kind")).lower() in ("comment", "t1") else "thread"
    items = []
    texts = [("title", _first(record, "title")), ("body", _first(record, "selftext", "body", "text", "content"))]
    for part, text in texts:
        text = str(text or "").strip()
        if text:
            items.append({"thread_id": thread_id, "kind_src": kind_src if part == "body" else "thread",
                          "subreddit": sub, "author": author, "text": text, "permalink": perm,
                          "created_at": created, "score": score})
    for c in record.get("comments") or []:
        if isinstance(c, dict):
            for it in explode({**c, "thread_id": thread_id, "subreddit": c.get("subreddit") or sub,
                               "permalink": c.get("permalink") or perm, "dataType": "comment"}):
                it["thread_id"] = thread_id
                items.append(it)
    return items


def load_records(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        data = data.get("opportunities") or data.get("items") or data.get("results") or data.get("data") or [data]
    return [d for d in data if isinstance(d, dict)]


def item_id(it: dict) -> str:
    return hashlib.sha1(f"{it['thread_id']}|{it['author']}|{it['text'][:120]}".encode()).hexdigest()[:20]


# ----------------------------------------------------------------------------- steps
def open_db(cfg: dict) -> sqlite3.Connection:
    base = Path(os.environ.get("GTM_DATA_DIR") or Path.home() / ".gtm" / "data").expanduser()
    path = Path(cfg.get("db") or base / "reddit_signals.db").expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def ingest(con, records: list[dict], vocab: Vocabulary, decay_cfg=None, taxonomy=None, now_dt=None) -> dict:
    decay_cfg = decay_cfg or signal_decay.load_config()
    taxonomy = taxonomy or signal_decay.load_taxonomy()
    stats = {"items": 0, "relevant": 0, "signals": 0, "by_kind": {}}
    for rec in records:
        for it in explode(rec):
            if not (12 <= len(it["text"]) <= 2000):
                continue
            iid = item_id(it)
            cur = con.execute("INSERT OR IGNORE INTO items VALUES (?,?,?,?,?,?,?,?,?,?)",
                              (iid, it["thread_id"], it["kind_src"], it["subreddit"], it["author"], it["text"],
                               it["permalink"], it["created_at"], it["score"],
                               datetime.now(timezone.utc).isoformat(timespec="seconds")))
            stats["items"] += cur.rowcount
            if not vocab.is_relevant(it["text"]):
                continue
            stats["relevant"] += 1
            kind = vocab.classify(it["text"])
            if not kind:
                continue
            sig = signal_decay.score_signal(KIND_TO_SIGNAL[kind], it["created_at"] or None, config=decay_cfg,
                                            taxonomy=taxonomy, now=now_dt)
            cur = con.execute("INSERT OR REPLACE INTO signals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                              (iid, iid, kind, KIND_TO_SIGNAL[kind], ",".join(vocab.brands_in(it["text"])),
                               ",".join(vocab.topics_in(it["text"])), it["text"][:600], it["subreddit"],
                               it["author"], it["permalink"], it["created_at"], it["score"], sig["freshness"],
                               sig["score"]))
            stats["signals"] += 1
            stats["by_kind"][kind] = stats["by_kind"].get(kind, 0) + 1
    con.commit()
    return stats


def cmd_pull(cfg: dict, con, vocab: Vocabulary, run=apify_client.run_actor) -> dict:
    ap = cfg.get("apify") or {}
    if not ap.get("actor"):
        sys.exit("config has no apify.actor; use `import` with an export file instead")
    items = run(ap["actor"], ap.get("input", {}), timeout=int(ap.get("timeout", 300)))
    if items is None:
        sys.exit("apify run failed")
    return ingest(con, items, vocab)


SIGNAL_COLS = ["signal_id", "kind", "brands", "topics", "quote", "subreddit", "author", "permalink",
               "created_at", "engagement", "freshness", "signal_score"]


def cmd_export(con, out: Path | None, vault_language: bool, include_expired: bool = False) -> dict:
    where = "" if include_expired else "WHERE freshness != 'Expired'"
    rows = [dict(r) for r in con.execute(f"SELECT * FROM signals {where} ORDER BY signal_score DESC, engagement DESC")]
    res = {"signals": len(rows)}
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=SIGNAL_COLS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        res["csv"] = str(out)
    if vault_language:
        existing = json.loads(VAULT_LANGUAGE.read_text()) if VAULT_LANGUAGE.exists() else []
        have = {e.get("id") for e in existing}
        sentiment = {"pain": "negative", "comparison": "neutral", "recommendation": "neutral", "question": "neutral"}
        added = 0
        for r in rows:
            if r["id"] in have or r["kind"] == "question":
                continue
            existing.append({"id": r["id"], "phrase": r["quote"][:280], "context": r["kind"],
                             "source": "reddit", "vertical": "", "sentiment": sentiment[r["kind"]],
                             "brands": r["brands"], "topics": r["topics"], "permalink": r["permalink"],
                             "date_captured": (r["created_at"] or "")[:10]})
            added += 1
        VAULT_LANGUAGE.write_text(json.dumps(existing, indent=2) + "\n")
        res["vault_language_added"] = added
    print(json.dumps(res))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["import", "pull", "export"])
    ap.add_argument("input", nargs="?", type=Path, help="import: export file (.json, .jsonl, .csv)")
    ap.add_argument("--config", type=Path, default=HERE / "reddit.json")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--vault-language", action="store_true", help="export: append phrases to the vault")
    ap.add_argument("--include-expired", action="store_true")
    args = ap.parse_args(argv)
    cfg = json.loads(args.config.read_text())
    vocab, con = Vocabulary(cfg), open_db(cfg)
    if args.cmd == "import":
        if not args.input:
            sys.exit("import needs an export file")
        print(json.dumps(ingest(con, load_records(args.input), vocab)))
    elif args.cmd == "pull":
        print(json.dumps(cmd_pull(cfg, con, vocab)))
    else:
        cmd_export(con, args.out or (None if args.vault_language else Path("reddit_signals.csv")),
                   args.vault_language, args.include_expired)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
