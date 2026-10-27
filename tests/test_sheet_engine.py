"""Sheet engine request planning: large fonts, formula escaping, color rules. No Google calls."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "lib"))
import sheet_engine as S  # noqa: E402


def font_sizes(reqs):
    out = []
    for r in reqs:
        fmt = r.get("repeatCell", {}).get("cell", {}).get("userEnteredFormat", {})
        if "fontSize" in fmt.get("textFormat", {}):
            out.append(fmt["textFormat"]["fontSize"])
    return out


class ValuesTests(unittest.TestCase):
    def test_formula_injection_escaped_numbers_kept(self):
        v = S.table_values([{"a": "=HYPERLINK(\"x\")", "b": "-5", "n": "3.0"}], ["a", "b", "n"], {"n"})
        self.assertEqual(v[1], ["'=HYPERLINK(\"x\")", "-5", 3])

    def test_none_and_nan_blank(self):
        self.assertEqual(S.table_values([{"a": None, "b": float("nan")}], ["a", "b"], set())[1], ["", ""])


class PlanTests(unittest.TestCase):
    def test_data_tab_fonts_are_large(self):
        vals = S.table_values([{"name": "x", "grade": "A"}], ["name", "grade"], set())
        sizes = font_sizes(S.plan_data_tab(7, vals))
        self.assertTrue(sizes and min(sizes) >= 12, sizes)

    def test_color_rules_and_widths(self):
        vals = S.table_values([{"grade": "A", "score": 4}], ["grade", "score"], {"score"})
        reqs = S.plan_data_tab(1, vals, {"grade": 150},
                               [{"type": "map", "col": "grade", "map": {"A": S.GREEN, "D": S.RED}},
                                {"type": "grad", "col": "score"}, {"type": "grad", "col": "missing"}])
        cf = [r for r in reqs if "addConditionalFormatRule" in r]
        self.assertEqual(len(cf), 3)
        widths = [r["updateDimensionProperties"]["properties"]["pixelSize"] for r in reqs
                  if r.get("updateDimensionProperties", {}).get("range", {}).get("dimension") == "COLUMNS"]
        self.assertEqual(widths[0], 150)

    def test_dashboard_title_and_kpis(self):
        values, reqs = S.plan_dashboard(2, {"title": "Gate", "sub": "10 leads"},
                                        [{"kind": "section", "label": "Routes"}, {"kind": "kpi", "label": "send", "value": 4}])
        self.assertEqual(values[0][0], "Gate")
        self.assertIn(S.FONTS["title"], font_sizes(reqs))
        self.assertIn(S.FONTS["kpi"], font_sizes(reqs))
        self.assertGreaterEqual(min(font_sizes(reqs)), 12)


if __name__ == "__main__":
    unittest.main()
