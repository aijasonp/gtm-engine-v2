"""Reddit buyer-language signals: vocabulary, classification, export shapes, vault language write."""
import csv
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "scripts" / "reddit-signals"))
import reddit_signals as R  # noqa: E402

CFG = {"brands": ["acmeguard", "shieldly", "hive"], "brand_aliases": {"acme guard": "acmeguard"},
       "category": ["ai security", "llm security", "dlp"], "topics": {"pricing": ["pricing", "per seat"]}}
V = R.Vocabulary(CFG)


def recent(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


class VocabularyTests(unittest.TestCase):
    def test_relevance_needs_brand_or_category(self):
        self.assertTrue(V.is_relevant("Anyone using LLM security tooling at work?"))
        self.assertFalse(V.is_relevant("Which mechanical keyboard should I buy?"))

    def test_short_brand_is_word_bounded(self):
        self.assertEqual(V.brands_in("our archive team"), [])
        self.assertCountEqual(V.brands_in("Hive vs Shieldly"), ["hive", "shieldly"])

    def test_alias_canonicalized(self):
        self.assertEqual(V.brands_in("we trialed Acme Guard"), ["acmeguard"])

    def test_classify_kinds(self):
        self.assertEqual(V.classify("Acmeguard vs Shieldly for a 2k-seat bank?"), "comparison")
        self.assertEqual(V.classify("Looking for an alternative to Acmeguard for AI security"), "recommendation")
        self.assertEqual(V.classify("Shieldly pricing is overpriced for what it does"), "pain")
        self.assertEqual(V.classify("How do you all handle DLP for copilots?"), "question")
        self.assertIsNone(V.classify("We rolled out AI security last year."))


class ImportTests(unittest.TestCase):
    def test_explode_nested_comments_and_permalink(self):
        items = R.explode({"id": "t1", "title": "Acmeguard vs Shieldly?", "selftext": "", "subreddit": "r/netsec",
                           "permalink": "/r/netsec/comments/t1/x", "created_utc": 1790000000,
                           "comments": [{"body": "Shieldly pricing is too expensive per seat", "author": "u2"}]})
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["permalink"], "https://www.reddit.com/r/netsec/comments/t1/x")
        self.assertEqual(items[1]["kind_src"], "comment")
        self.assertEqual(items[0]["subreddit"], "netsec")

    def test_ingest_export_and_vault_language(self):
        records = [
            {"id": "a", "title": "Acmeguard vs Shieldly for AI security?", "createdAt": recent(3), "url": "https://r/a"},
            {"id": "b", "title": "Shieldly pricing is overpriced for LLM security", "createdAt": recent(10), "url": "https://r/b"},
            {"id": "c", "title": "Best pizza in Dallas?", "createdAt": recent(1), "url": "https://r/c"},
            {"id": "d", "title": "Hive vs Acmeguard, old thread", "createdAt": recent(200), "url": "https://r/d"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            con = R.open_db({"db": str(Path(tmp) / "r.db")})
            stats = R.ingest(con, records, V)
            self.assertEqual(stats["signals"], 3)
            self.assertEqual(R.ingest(con, records, V)["items"], 0, "re-import is idempotent")
            lang = Path(tmp) / "community-language.json"
            with mock.patch.object(R, "VAULT_LANGUAGE", lang):
                res = R.cmd_export(con, Path(tmp) / "s.csv", vault_language=True)
                again = R.cmd_export(con, None, vault_language=True)
            self.assertEqual(res["signals"], 2, "expired signal left out")
            self.assertEqual(again["vault_language_added"], 0)
            with (Path(tmp) / "s.csv").open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["signal_id"], "reddit-vendor-comparison")
            entries = json.loads(lang.read_text())
            self.assertEqual({e["sentiment"] for e in entries}, {"neutral", "negative"})


if __name__ == "__main__":
    unittest.main()
