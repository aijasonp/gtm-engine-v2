"""Reachability gate: waterfall routing, header aliases, verifier deltas, cache and the CLI end to end.
No network: every MoltSets call goes through a fake caller."""
import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "scripts" / "reachability-gate"))
import gate  # noqa: E402
import moltsets_client as M  # noqa: E402


def lead(**kw):
    base = {"first_name": "Dana", "last_name": "Reyes", "company": "Acme", "domain": "acme.com",
            "email": "dana@acme.com", "linkedin_url": "https://www.linkedin.com/in/dana", "title": "VP Security",
            "verifier_status": "", "_raw": {}}
    base.update(kw)
    return base


class FakeCaller:
    """endpoint -> (status, results) map; records every call."""

    def __init__(self, responses):
        self.responses, self.calls = responses, []

    def __call__(self, endpoint, body):
        self.calls.append(endpoint)
        st, res = self.responses.get(endpoint, (404, {}))
        return st, res, {}


class WaterfallTests(unittest.TestCase):
    def test_linkedin_lookup_grades_and_stops(self):
        call = FakeCaller({"reverse_linkedin_lookup": (200, {"company": {"name": "Acme", "domain": "acme.com"},
                                                             "work_email_confirmed": "dana@acme.com",
                                                             "work_email_confirmed_risk_score": "A"})})
        r = gate.grade_row(lead(), call)
        self.assertEqual((r["grade"], r["tier"], r["route"]), ("A", "T1_send", "email"))
        self.assertEqual(call.calls, ["reverse_linkedin_lookup"])

    def test_job_change_goes_to_resource_and_skips_email_lookup(self):
        call = FakeCaller({"reverse_linkedin_lookup": (200, {"company": {"name": "Globex", "domain": "globex.com"}})})
        r = gate.grade_row(lead(), call)
        self.assertEqual((r["still_at_company"], r["route"]), ("moved", "resource"))
        self.assertNotIn("reverse_email_lookup", call.calls)

    def test_catch_all_routes_low_volume(self):
        call = FakeCaller({"reverse_email_lookup": (200, {"work_email_confirmed": "dana@acme.com",
                                                          "work_email_confirmed_risk_score": "C"})})
        r = gate.grade_row(lead(linkedin_url=""), call)
        self.assertEqual(r["route"], "email_low_volume")

    def test_hard_invalid_routes_linkedin_then_phone(self):
        call = FakeCaller({"reverse_email_lookup": (200, {"work_email_confirmed": "dana@acme.com",
                                                          "work_email_confirmed_risk_score": "D"})})
        r = gate.grade_row(lead(), call)
        self.assertEqual((r["tier"], r["route"]), ("SUPPRESS", "linkedin_then_phone"))

    def test_second_pass_recovers_same_domain_address(self):
        call = FakeCaller({"search_business_profile_by_name": (200, {
            "first_name": "Dana", "last_name": "Reyes", "work_email_confirmed": "d.reyes@acme.com",
            "work_email_confirmed_risk_score": "B"})})
        r = gate.grade_row(lead(linkedin_url=""), call, second_pass=True)
        self.assertEqual((r["tier"], r["email"], r["corrected"]), ("T1_send_corrected", "d.reyes@acme.com", "yes"))

    def test_second_pass_never_adopts_other_domain(self):
        call = FakeCaller({"search_business_profile_by_name": (200, {
            "first_name": "Dana", "last_name": "Reyes", "work_email_confirmed": "dana@oldjob.com",
            "work_email_confirmed_risk_score": "A"})})
        r = gate.grade_row(lead(linkedin_url=""), call, second_pass=True)
        self.assertEqual(r["email"], "dana@acme.com")
        self.assertNotEqual(r["route"], "email")

    def test_not_in_graph_without_second_pass_goes_linkedin(self):
        r = gate.grade_row(lead(), FakeCaller({}))
        self.assertEqual(r["route"], "linkedin")

    def test_free_mail_held(self):
        r = gate.grade_row(lead(email="dana@gmail.com", linkedin_url="", domain="acme.com"), FakeCaller({}))
        self.assertEqual(r["route"], "hold")

    def test_verifier_delta_downgrade(self):
        call = FakeCaller({"reverse_email_lookup": (200, {"work_email_confirmed": "dana@acme.com",
                                                          "work_email_confirmed_risk_score": "D"})})
        r = gate.grade_row(lead(linkedin_url="", verifier_status="deliverable"), call)
        self.assertEqual(r["delta_class"], "molt_downgrades_valid")

    def test_floor_guard_stops_calls(self):
        b = M.Budget(records_floor=25)
        b.records_5h = 10
        call = FakeCaller({})
        gate.grade_row(lead(), call, budget=b)
        self.assertEqual(call.calls, [])


class NormalizeTests(unittest.TestCase):
    def test_clay_and_hubspot_headers(self):
        r = gate.normalize_row({"Full Name": "Ana Lima", "Work Email": "ANA@Example.io", "Website": "https://www.example.io/",
                                "hs_linkedin_url": "https://linkedin.com/in/ana", "zb_status": "catch-all"})
        self.assertEqual((r["first_name"], r["last_name"], r["email"], r["domain"]),
                         ("Ana", "Lima", "ana@example.io", "example.io"))
        self.assertEqual(r["verifier_status"], "catch-all")

    def test_domain_falls_back_to_email_not_freemail(self):
        self.assertEqual(gate.normalize_row({"email": "x@acme.com"})["domain"], "acme.com")
        self.assertEqual(gate.normalize_row({"email": "x@gmail.com"})["domain"], "")


class KeyTests(unittest.TestCase):
    def test_env_file_inline_comment_is_not_a_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text("MOLTSETS_API_KEY=            # fill me in\n")
            with mock.patch.dict(os.environ, {"GTM_ENV_FILE": str(env), "MOLTSETS_API_KEY": ""}):
                self.assertIsNone(M.get_key())
            env.write_text("export MOLTSETS_API_KEY=\"abc123\"  # prod\n")
            with mock.patch.dict(os.environ, {"GTM_ENV_FILE": str(env), "MOLTSETS_API_KEY": ""}):
                self.assertEqual(M.get_key(), "abc123")


class EndToEndTests(unittest.TestCase):
    def test_cli_writes_route_files_and_uses_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = tmp / "clay.csv"
            with src.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["first_name", "last_name", "email", "company", "domain", "campaign"])
                w.writeheader()
                w.writerow({"first_name": "A", "last_name": "One", "email": "a@acme.com", "company": "Acme",
                            "domain": "acme.com", "campaign": "q4"})
                w.writerow({"first_name": "B", "last_name": "Two", "email": "b@acme.com", "company": "Acme",
                            "domain": "acme.com", "campaign": "q4"})
            grades = {"a@acme.com": "A", "b@acme.com": "C"}
            calls = []

            def fake_call(endpoint, body, key=None, timeout=45):
                calls.append(endpoint)
                e = body.get("email")
                return 200, {"work_email_confirmed": e, "work_email_confirmed_risk_score": grades[e]}, {}

            env = {"REACHABILITY_DB": str(tmp / "r.db"), "MOLTSETS_API_KEY": "test"}
            with mock.patch.dict(os.environ, env), mock.patch.object(M, "call", fake_call), \
                    mock.patch.object(M, "pause", lambda: None):
                gate.main([str(src), "--out-dir", str(tmp / "out")])
                self.assertEqual(len(calls), 2)
                gate.main([str(src), "--out-dir", str(tmp / "out2")])
                self.assertEqual(len(calls), 2, "second run must come from cache")
            with (tmp / "out" / "send.csv").open() as f:
                send = list(csv.DictReader(f))
            with (tmp / "out" / "send_low_volume.csv").open() as f:
                low = list(csv.DictReader(f))
            self.assertEqual([r["email"] for r in send], ["a@acme.com"])
            self.assertEqual([r["email"] for r in low], ["b@acme.com"])
            self.assertEqual(send[0]["campaign"], "q4", "unknown input columns pass through")
            summary = json.loads((tmp / "out2" / "summary.json").read_text())
            self.assertEqual(summary["from_cache"], 2)


if __name__ == "__main__":
    unittest.main()
