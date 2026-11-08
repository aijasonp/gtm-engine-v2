#!/usr/bin/env python3
"""engagers.py: turn people who comment on competitor LinkedIn posts into scored, Clay-ready leads.

Adapted from the nexus-intel engager pipeline in shawnla90/gtm-coding-agent (MIT; see THIRD_PARTY.md).
Feeds the vault's `community-intent` category:
  competitor-post-engagement   commented on one tracked competitor's post
  competitor-multi-engagement  commented on posts from two or more tracked competitors

Steps:
  pull    fetch recent posts from each competitor's company page and exec profiles, then the
          commenters on those posts (Apify harvestapi actors). Stored in SQLite, deduplicated.
  score   drop competitor employees, your own people, sellers and recruiters; tier the persona;
          apply decay-config.json freshness; write one signal per person.
  export  CSV with the columns the Clay dispatch table expects (only push=yes rows by default).

  python3 engagers.py pull   --config competitors.json            # spends Apify credits
  python3 engagers.py pull   --config competitors.json --dry-run  # plan only
  python3 engagers.py score  --config competitors.json
  python3 engagers.py export --config competitors.json --out competitor_engagers.csv
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
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "lib"))
import apify_client  # noqa: E402
import signal_decay  # noqa: E402

ACTOR_COMPANY_POSTS = "harvestapi/linkedin-company-posts"
ACTOR_PROFILE_POSTS = "harvestapi/linkedin-profile-posts"
ACTOR_COMMENTS = "harvestapi/linkedin-post-comments"

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
  url TEXT PRIMARY KEY, competitor TEXT, source TEXT, published_at TEXT, body TEXT,
  comments INTEGER, fetched_at TEXT, comments_fetched_at TEXT);
CREATE TABLE IF NOT EXISTS people (
  profile_url TEXT PRIMARY KEY, name TEXT, title TEXT, company TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS engagements (
  id TEXT PRIMARY KEY, profile_url TEXT, post_url TEXT, competitor TEXT, comment TEXT, engaged_at TEXT);
CREATE TABLE IF NOT EXISTS engager_scores (
  profile_url TEXT PRIMARY KEY, name TEXT, title TEXT, company TEXT, persona_tier INTEGER,
  excluded TEXT, competitors TEXT, competitor_count INTEGER, comments INTEGER, last_engaged_at TEXT,
  signal_id TEXT, freshness TEXT, signal_score REAL, priority REAL, push TEXT, sample_comment TEXT,
  scored_at TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_config(path: Path) -> dict:
    cfg = json.loads(Path(path).read_text())
    cfg.setdefault("lookback_days", 30)
    cfg.setdefault("max_posts_per_source", 10)
    cfg.setdefault("max_comments_per_post", 50)
    cfg.setdefault("min_persona_tier", 3)
    return cfg


def db_path(cfg: dict) -> Path:
    base = Path(os.environ.get("GTM_DATA_DIR") or Path.home() / ".gtm" / "data").expanduser()
    return Path(cfg.get("db") or base / "competitor_engagers.db").expanduser()


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


# ----------------------------------------------------------------------------- normalizers (pure)
def slug(url: str) -> str:
    return (url or "").rstrip("/").split("/")[-1]


def clean_profile_url(url: str) -> str:
    u = (url or "").split("?")[0].rstrip("/")
    return u.replace("http://", "https://").replace("://linkedin.com", "://www.linkedin.com")


def parse_date(value) -> str:
    """UTC ISO timestamp from harvestapi's mixed date shapes (ISO, date-only, epoch s/ms, {date: ...}), or ''."""
    if isinstance(value, dict):
        value = value.get("date") or value.get("timestamp") or value.get("iso")
    if value in (None, ""):
        return ""
    dt = None
    if isinstance(value, (int, float)) or str(value).strip().isdigit():
        v = float(value)
        try:
            dt = datetime.fromtimestamp(v / 1000 if v > 1e12 else v, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return ""
    else:
        s = str(value).strip()
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = datetime.strptime(s[:10], "%Y-%m-%d")
            except ValueError:
                return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def normalize_post(item: dict) -> dict:
    eng = item.get("engagement") if isinstance(item.get("engagement"), dict) else {}
    return {"url": item.get("linkedinUrl") or item.get("url") or item.get("postUrl") or "",
            "published_at": parse_date(item.get("postedAt") or item.get("publishedAt") or item.get("createdAt")),
            "body": (item.get("content") or item.get("text") or item.get("commentary") or "")[:2000],
            "comments": int(eng.get("comments") or item.get("numComments") or 0)}


def normalize_comment(item: dict) -> dict:
    actor = item.get("actor") or item.get("author") or {}
    q = item.get("query")
    post_url = q.get("post", "") if isinstance(q, dict) else (q or item.get("postUrl") or "")
    return {"profile_url": clean_profile_url(actor.get("linkedinUrl") or actor.get("profileUrl") or ""),
            "name": actor.get("name") or "",
            "title": actor.get("position") or actor.get("headline") or "",
            "company": actor.get("company") or "",
            "comment": (item.get("commentary") or item.get("text") or "")[:1000],
            "post_url": post_url,
            "engaged_at": parse_date(item.get("createdAt") or item.get("postedAt"))}


# ----------------------------------------------------------------------------- scoring (pure)
def _has(text: str, keywords) -> bool:
    t = (text or "").lower()
    return any(re.search(r"\b" + re.escape(k.lower()) + r"\b", t) for k in keywords or [])


def persona_tier(title: str, tiers: dict) -> int:
    for tier in sorted((int(k) for k in tiers), reverse=True):
        if _has(title, tiers[str(tier)]):
            return tier
    return 1


def exclusion(person: dict, cfg: dict) -> str:
    """'' when the person is a prospect, else the reason they are not."""
    blob = f"{person.get('title', '')} {person.get('company', '')}"
    for comp in cfg.get("competitors", []):
        if _has(blob, comp.get("keywords") or [comp["name"]]):
            return f"works_at_competitor:{comp['name']}"
    if _has(blob, cfg.get("own_company_keywords")):
        return "own_company"
    if _has(person.get("title", ""), cfg.get("exclude_title_keywords")):
        return "excluded_title"
    if not person.get("profile_url"):
        return "no_profile_url"
    return ""


def score_person(person: dict, engagements: list[dict], cfg: dict, decay_cfg=None, taxonomy=None,
                 now_dt: datetime | None = None) -> dict:
    competitors = sorted({e["competitor"] for e in engagements})
    last = max((e["engaged_at"] for e in engagements if e.get("engaged_at")), default="")
    signal_id = "competitor-multi-engagement" if len(competitors) >= 2 else "competitor-post-engagement"
    sig = signal_decay.score_signal(signal_id, last or None, config=decay_cfg, taxonomy=taxonomy, now=now_dt)
    tier = persona_tier(person.get("title", ""), cfg.get("persona_tiers", {}))
    excl = exclusion(person, cfg)
    depth = min(1.0, 0.6 + 0.1 * len(engagements))          # 1 comment 0.7 ... 4+ comments 1.0
    priority = round(sig["score"] * (tier / 5) * depth, 3)
    push = "yes" if (not excl and tier >= cfg.get("min_persona_tier", 3) and sig["freshness"] != "Expired") else "no"
    sample = max(engagements, key=lambda e: len(e.get("comment") or ""), default={}).get("comment", "")
    return {"profile_url": person["profile_url"], "name": person.get("name", ""), "title": person.get("title", ""),
            "company": person.get("company", ""), "persona_tier": tier, "excluded": excl,
            "competitors": ",".join(competitors), "competitor_count": len(competitors), "comments": len(engagements),
            "last_engaged_at": last, "signal_id": signal_id, "freshness": sig["freshness"],
            "signal_score": sig["score"], "priority": priority, "push": push, "sample_comment": sample[:280],
            "scored_at": now()}


# ----------------------------------------------------------------------------- steps
def cmd_pull(cfg: dict, con: sqlite3.Connection, run=apify_client.run_actor, dry_run: bool = False) -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=cfg["lookback_days"])).isoformat(timespec="seconds")
    sources = [(c["name"], u, "company" if "/company/" in u else "profile")
               for c in cfg.get("competitors", []) for u in c.get("linkedin", [])]
    print(f"{len(sources)} competitor sources, lookback {cfg['lookback_days']}d")
    if dry_run:
        for s in sources:
            print(f"  would pull {s[2]} posts: {s[0]} {s[1]}")
        return {"sources": len(sources)}
    stats = {"posts": 0, "comments": 0, "people": 0}
    for comp, url, kind in sources:
        actor, field = (ACTOR_COMPANY_POSTS, "companyPublicIdentifiers") if kind == "company" \
            else (ACTOR_PROFILE_POSTS, "profilePublicIdentifiers")
        items = run(actor, {field: [slug(url)], "maxItems": cfg["max_posts_per_source"]}) or []
        for it in items:
            p = normalize_post(it)
            if not p["url"]:
                continue
            if p["published_at"] and p["published_at"] < cutoff:
                continue
            cur = con.execute("INSERT OR IGNORE INTO posts (url, competitor, source, published_at, body, comments, "
                              "fetched_at) VALUES (?,?,?,?,?,?,?)",
                              (p["url"], comp, url, p["published_at"], p["body"], p["comments"], now()))
            stats["posts"] += cur.rowcount
        con.commit()
    todo = con.execute("SELECT url, competitor FROM posts WHERE comments_fetched_at IS NULL").fetchall()
    for i in range(0, len(todo), 15):
        batch = todo[i:i + 15]
        comp_of = {r["url"]: r["competitor"] for r in batch}
        items = run(ACTOR_COMMENTS, {"posts": list(comp_of), "maxItems": cfg["max_comments_per_post"],
                                     "scrapeReplies": True, "profileScraperMode": "short"})
        if items is None:
            continue
        for it in items:
            c = normalize_comment(it)
            if not c["profile_url"] or c["post_url"] not in comp_of:
                continue
            had = con.execute("SELECT 1 FROM people WHERE profile_url=?", (c["profile_url"],)).fetchone()
            con.execute("INSERT INTO people (profile_url, name, title, company, updated_at) VALUES (?,?,?,?,?) "
                        "ON CONFLICT(profile_url) DO UPDATE SET name=COALESCE(NULLIF(excluded.name,''),name), "
                        "title=COALESCE(NULLIF(excluded.title,''),title), "
                        "company=COALESCE(NULLIF(excluded.company,''),company), updated_at=excluded.updated_at",
                        (c["profile_url"], c["name"], c["title"], c["company"], now()))
            stats["people"] += 0 if had else 1
            eid = hashlib.sha1(f"{c['profile_url']}|{c['post_url']}|{c['comment'][:80]}".encode()).hexdigest()[:20]
            cur = con.execute("INSERT OR IGNORE INTO engagements VALUES (?,?,?,?,?,?)",
                              (eid, c["profile_url"], c["post_url"], comp_of[c["post_url"]], c["comment"],
                               c["engaged_at"]))
            stats["comments"] += cur.rowcount
        con.executemany("UPDATE posts SET comments_fetched_at=? WHERE url=?", [(now(), u) for u in comp_of])
        con.commit()
    print(json.dumps(stats))
    return stats


def cmd_score(cfg: dict, con: sqlite3.Connection) -> dict:
    decay_cfg, taxonomy = signal_decay.load_config(), signal_decay.load_taxonomy()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=cfg["lookback_days"])).isoformat(timespec="seconds")
    counts = {"scored": 0, "push": 0, "excluded": 0}
    for p in con.execute("SELECT * FROM people").fetchall():
        engs = [dict(e) for e in con.execute("SELECT * FROM engagements WHERE profile_url=?", (p["profile_url"],))]
        recent = [e for e in engs if not e["engaged_at"] or e["engaged_at"] >= cutoff] or engs
        s = score_person(dict(p), recent, cfg, decay_cfg, taxonomy)
        con.execute(f"INSERT OR REPLACE INTO engager_scores ({','.join(s)}) VALUES ({','.join('?' * len(s))})",
                    tuple(s.values()))
        counts["scored"] += 1
        counts["push"] += s["push"] == "yes"
        counts["excluded"] += bool(s["excluded"])
    con.commit()
    print(json.dumps(counts))
    return counts


EXPORT_COLS = ["name", "first_name", "last_name", "title", "company", "linkedin_url", "persona_tier",
               "competitors", "competitor_count", "comments", "last_engaged_at", "signal_id", "freshness",
               "signal_score", "priority", "sample_comment"]


def cmd_export(con: sqlite3.Connection, out: Path, include_all: bool = False) -> int:
    where = "" if include_all else "WHERE push='yes'"
    rows = con.execute(f"SELECT * FROM engager_scores {where} ORDER BY priority DESC").fetchall()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EXPORT_COLS + (["push", "excluded"] if include_all else []),
                           extrasaction="ignore")
        w.writeheader()
        for r in rows:
            d = dict(r)
            parts = (d["name"] or "").split()
            d.update(first_name=parts[0] if parts else "", last_name=" ".join(parts[1:]),
                     linkedin_url=d["profile_url"])
            w.writerow(d)
    print(f"wrote {len(rows)} rows to {out}")
    return len(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["pull", "score", "export"])
    ap.add_argument("--config", type=Path, default=HERE / "competitors.json")
    ap.add_argument("--out", type=Path, default=Path("competitor_engagers.csv"))
    ap.add_argument("--all", action="store_true", help="export: include excluded and low-tier rows")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    con = open_db(db_path(cfg))
    if args.cmd == "pull":
        if not args.dry_run and not apify_client.get_token():
            sys.exit("APIFY_TOKEN not set: export it or add it to GTM_ENV_FILE")
        cmd_pull(cfg, con, dry_run=args.dry_run)
    elif args.cmd == "score":
        cmd_score(cfg, con)
    else:
        cmd_export(con, args.out, args.all)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
