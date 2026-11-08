"""Competitor engager mining: normalizers, exclusions, persona tiers, scoring, and pull/score/export
end to end against a fake Apify runner."""
import csv
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "scripts" / "competitor-engagers"))
import engagers as E  # noqa: E402

CFG = {
    "own_company_keywords": ["Northwind"],
    "competitors": [
        {"name": "RivalOne", "keywords": ["rivalone"], "linkedin": ["https://www.linkedin.com/company/rivalone/"]},
        {"name": "RivalTwo", "keywords": ["rivaltwo"], "linkedin": ["https://www.linkedin.com/in/rivaltwo-ceo/"]},
    ],
    "persona_tiers": {"5": ["ciso"], "4": ["vp security"], "3": ["director"], "2": ["manager"]},
    "exclude_title_keywords": ["recruiter"],
    "min_persona_tier": 3, "lookback_days": 30, "max_posts_per_source": 5, "max_comments_per_post": 20,
}


def iso(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


class PureTests(unittest.TestCase):
    def test_parse_date_shapes(self):
        self.assertTrue(E.parse_date({"date": "2026-10-01T10:00:00.000Z"}).startswith("2026-10-01T10:00:00"))
        self.assertTrue(E.parse_date(1790000000000).startswith("2026-"))
        self.assertEqual(E.parse_date("2026-10-01"), "2026-10-01T00:00:00+00:00")
        self.assertEqual(E.parse_date("garbage"), "")

    def test_normalize_comment(self):
        c = E.normalize_comment({"actor": {"linkedinUrl": "http://linkedin.com/in/pat/?trk=x", "name": "Pat Q",
                                           "position": "CISO at Initech"},
                                 "commentary": "Great point", "query": {"post": "https://li/p/1"},
                                 "createdAt": "2026-10-20T00:00:00Z"})
        self.assertEqual(c["profile_url"], "https://www.linkedin.com/in/pat")
        self.assertEqual(c["post_url"], "https://li/p/1")

    def test_exclusions(self):
        self.assertTrue(E.exclusion({"title": "AE at RivalOne", "profile_url": "u"}, CFG).startswith("works_at_competitor"))
        self.assertEqual(E.exclusion({"title": "Director, Northwind", "profile_url": "u"}, CFG), "own_company")
        self.assertEqual(E.exclusion({"title": "Technical Recruiter", "profile_url": "u"}, CFG), "excluded_title")
        self.assertEqual(E.exclusion({"title": "CISO", "company": "Initech", "profile_url": "u"}, CFG), "")

    def test_persona_tier_word_boundary(self):
        self.assertEqual(E.persona_tier("CISO, Initech", CFG["persona_tiers"]), 5)
        self.assertEqual(E.persona_tier("Directory Services Engineer", CFG["persona_tiers"]), 1)

    def test_multi_competitor_is_high_signal(self):
        person = {"profile_url": "u", "name": "Pat", "title": "VP Security", "company": "Initech"}
        engs = [{"competitor": "RivalOne", "engaged_at": iso(2), "comment": "a"},
                {"competitor": "RivalTwo", "engaged_at": iso(5), "comment": "longer comment"}]
        s = E.score_person(person, engs, CFG)
        self.assertEqual((s["signal_id"], s["freshness"], s["push"]), ("competitor-multi-engagement", "Fresh", "yes"))
        self.assertEqual(s["sample_comment"], "longer comment")

    def test_low_tier_not_pushed(self):
        s = E.score_person({"profile_url": "u", "title": "Manager"},
                           [{"competitor": "RivalOne", "engaged_at": iso(1), "comment": ""}], CFG)
        self.assertEqual(s["push"], "no")


class PipelineTests(unittest.TestCase):
    def test_pull_score_export(self):
        def fake_run(actor, actor_input, **_):
            if actor == E.ACTOR_COMPANY_POSTS:
                return [{"linkedinUrl": "https://li/p/1", "postedAt": {"date": iso(3)}, "content": "launch"},
                        {"linkedinUrl": "https://li/p/old", "postedAt": {"date": iso(90)}, "content": "old"}]
            if actor == E.ACTOR_PROFILE_POSTS:
                return [{"linkedinUrl": "https://li/p/2", "postedAt": {"date": iso(4)}, "content": "opinion"}]
            out = []
            for post in actor_input["posts"]:
                out.append({"actor": {"linkedinUrl": "https://www.linkedin.com/in/pat", "name": "Pat Quinn",
                                      "position": "CISO at Initech"}, "commentary": f"on {post}",
                            "query": {"post": post}, "createdAt": iso(2)})
                out.append({"actor": {"linkedinUrl": "https://www.linkedin.com/in/sam", "name": "Sam Lee",
                                      "position": "Account Executive at RivalOne"}, "commentary": "+1",
                            "query": {"post": post}, "createdAt": iso(2)})
            return out

        with tempfile.TemporaryDirectory() as tmp:
            con = E.open_db(Path(tmp) / "e.db")
            stats = E.cmd_pull(CFG, con, run=fake_run)
            self.assertEqual(stats["posts"], 2, "post older than lookback is skipped")
            E.cmd_pull(CFG, con, run=fake_run)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM engagements").fetchone()[0], 4, "re-pull is idempotent")
            E.cmd_score(CFG, con)
            out = Path(tmp) / "out.csv"
            self.assertEqual(E.cmd_export(con, out), 1)
            with out.open() as f:
                row = next(csv.DictReader(f))
            self.assertEqual((row["first_name"], row["signal_id"], row["competitor_count"]),
                             ("Pat", "competitor-multi-engagement", "2"))

    def test_db_path_respects_env(self):
        with mock.patch.dict(os.environ, {"GTM_DATA_DIR": "/tmp/x"}):
            self.assertEqual(E.db_path({}), Path("/tmp/x/competitor_engagers.db"))


if __name__ == "__main__":
    unittest.main()
