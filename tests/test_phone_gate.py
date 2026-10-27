"""Phone compliance gate: normalization, toll-free, main line, line type, DNC hash matching."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "scripts" / "phone-compliance"))
import phone_gate as P  # noqa: E402


class NormalizeTests(unittest.TestCase):
    def test_us_formats(self):
        for raw in ("(214) 555-0142", "214.555.0142", "1-214-555-0142", "+1 214 555 0142", "214-555-0142 x12"):
            self.assertEqual(P.to_e164(raw), "+12145550142", raw)

    def test_international_and_garbage(self):
        self.assertEqual(P.to_e164("+44 20 7946 0958"), "+442079460958")
        self.assertEqual(P.to_e164("0044 20 7946 0958"), "+442079460958")
        self.assertEqual(P.to_e164("12345"), "")
        self.assertEqual(P.to_e164(""), "")

    def test_hash_is_format_independent(self):
        self.assertEqual(P.hash_number("(214) 555-0142"), P.hash_number("+12145550142"))


class CheckTests(unittest.TestCase):
    DNC = {P.hash_number("+12145550199")}

    def test_cleared(self):
        self.assertEqual(P.check_number("214-555-0142", email="a@b.com", dnc=self.DNC)[0], P.CLEARED)

    def test_toll_free(self):
        self.assertEqual(P.check_number("1-800-555-0142", email="a@b.com", dnc=self.DNC)[:2],
                         (P.EMAIL_ONLY, "toll_free"))

    def test_main_line(self):
        r = P.check_number("2145550142", main_line="(214) 555-0142", dnc=self.DNC)
        self.assertEqual(r[:2], (P.NO_CHANNEL, "company_main_line"))

    def test_dnc_match(self):
        self.assertEqual(P.check_number("214 555 0199", email="x@y.com", dnc=self.DNC)[:2], (P.EMAIL_ONLY, "dnc_match"))

    def test_no_dnc_loaded_is_pending_not_cleared(self):
        self.assertEqual(P.check_number("214 555 0142", dnc=None)[:2], (P.PENDING, "dnc_not_loaded"))

    def test_landline_rejected_and_missing_type_held_when_required(self):
        self.assertEqual(P.check_number("2145550142", line_type="landline", dnc=self.DNC)[1], "line_type_landline")
        self.assertEqual(P.check_number("2145550142", dnc=self.DNC, require_line_type=True)[0], P.PENDING)


class FileTests(unittest.TestCase):
    def test_dnc_file_accepts_hashes_or_raw_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "dnc.txt"
            f.write_text(f"# internal list\n{P.hash_number('+12145550199')}\n(972) 555-0100\n")
            hashes = P.load_dnc([f])
            self.assertIn(P.hash_number("9725550100"), hashes)
            self.assertIn(P.hash_number("2145550199"), hashes)

    def test_check_cli_splits_cleared(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "dnc.txt").write_text(P.hash_number("2145550199") + "\n")
            with (tmp / "phones.csv").open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["email", "mobilephone"])
                w.writerows([["a@x.com", "214-555-0142"], ["b@x.com", "214-555-0199"], ["c@x.com", "888-555-0100"]])
            P.main(["check", str(tmp / "phones.csv"), "--dnc", str(tmp / "dnc.txt"), "--out-dir", str(tmp)])
            with (tmp / "cleared_to_call.csv").open() as f:
                cleared = list(csv.DictReader(f))
            self.assertEqual([r["email"] for r in cleared], ["a@x.com"])
            self.assertEqual(cleared[0]["phone_e164"], "+12145550142")


if __name__ == "__main__":
    unittest.main()
