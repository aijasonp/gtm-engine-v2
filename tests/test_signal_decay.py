"""Vault taxonomy integrity and decay scoring."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "lib"))
import signal_decay as D  # noqa: E402

NOW = datetime(2026, 10, 27, tzinfo=timezone.utc)


class TaxonomyTests(unittest.TestCase):
    def setUp(self):
        self.tax, self.cfg = D.load_taxonomy(), D.load_config()

    def test_signal_ids_unique(self):
        ids = [s["signal_id"] for c in self.tax["categories"] for s in c["signals"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_category_has_weight_and_override(self):
        weights = self.cfg["composite_score_formula"]["category_priority_weights"]
        for c in self.tax["categories"]:
            self.assertIn(str(c["priority"]), weights, c["category_id"])
            self.assertIn(c["category_id"], self.cfg["category_overrides"], c["category_id"])

    def test_community_intent_signals_present(self):
        for sid in ("competitor-post-engagement", "competitor-multi-engagement", "reddit-vendor-comparison",
                    "reddit-recommendation-ask", "reddit-vendor-pain", "reddit-category-question"):
            cat, _ = D.signal_def(sid, self.tax)
            self.assertEqual(cat["category_id"], "community-intent")


class ScoreTests(unittest.TestCase):
    def test_freshness_bands(self):
        s = lambda days: D.score_signal("competitor-multi-engagement", NOW - timedelta(days=days), now=NOW)  # noqa: E731
        self.assertEqual(s(3)["freshness"], "Fresh")
        self.assertEqual(s(20)["freshness"], "Warm")
        self.assertEqual(s(31)["freshness"], "Expired")
        self.assertEqual(s(3)["score"], 0.55)

    def test_unknown_signal_fails_loudly(self):
        with self.assertRaises(KeyError):
            D.score_signal("not-a-signal", NOW, now=NOW)

    def test_unknown_age_is_stale(self):
        self.assertEqual(D.score_signal("reddit-vendor-pain", None, now=NOW)["freshness"], "Stale")

    def test_epoch_seconds_and_ms(self):
        ts = int((NOW - timedelta(days=2)).timestamp())
        self.assertEqual(D.age_days(str(ts), NOW), 2)
        self.assertEqual(D.age_days(str(ts * 1000), NOW), 2)

    def test_account_tier(self):
        self.assertEqual(D.account_tier(2.6), "tier1_enterprise")
        self.assertEqual(D.account_tier(0.1), "below_threshold")


if __name__ == "__main__":
    unittest.main()
