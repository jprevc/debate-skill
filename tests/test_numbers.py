"""The NUMBER check (numcheck.py, run by report_html.py) on Report prose and figure values, and evidence.py calc.

Run: uv run --with markdown==3.7 --with pytest==9.2.0 pytest tests
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "debate" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import numcheck  # noqa: E402


def evidence(eid, quote, context="", result="passed"):
    audit = f"\n## Audit\n\n- Result: {result}\n- Quote found: yes\n- Supports: yes\n- Cherry-picked: no\n- Source Tier: A\n"
    ctx = f"## Context\n\nBefore:\n\n> {context}\n\n" if context else ""
    return f"---\nid: {eid}\nadded_by: {eid.split('-')[1]}\ntitle: T\npublisher: P\nurl: https://example.org/x\n---\n\n## Quote\n\n> {quote}\n\n{ctx}{audit}"


def found(sentence, quote):
    return numcheck.matches(numcheck.numbers(sentence)[0], numcheck.numbers(quote, quantities_only=False))


class Matching(unittest.TestCase):
    def test_scale_words_and_conventions_are_read_across_languages(self):
        self.assertTrue(found("EUR 1.2 billion", "SKUPAJ 1.195 mio EUR"))
        self.assertTrue(found("EUR 79 million", "79"))  # a table headed "mio EUR"
        self.assertTrue(found("36.83%", "znaša 36,83 %"))
        self.assertTrue(found("EUR 70,000", "do 70.000 eurov"))
        self.assertTrue(found("a loss of EUR 53 million", "−53"))

    def test_rounding_is_to_the_prose_precision_only(self):
        self.assertTrue(found("about EUR 80 million", "79,6 mio"))
        self.assertTrue(found("8,167", "= 8167.04"))
        self.assertFalse(found("EUR 80 million", "75 mio"))
        self.assertTrue(found("0.13%", "0.125"))  # half rounds up, as writers round
        self.assertFalse(found("0.13%", "0.124"))

    def test_references_are_not_quantities(self):
        text = ("Under Art. 25 ZRLI, in U-I-79/25 (decided 6:3) on 1 March 2026, for 2024-25, 25. in 26. člen, "
                "see E-PRO-A-012 and para. 37 of Table 1.1")
        self.assertEqual(numcheck.numbers(text), [])


class Prose(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ev = Path(self.tmp.name)
        (self.ev / "E-CON-001.md").write_text(evidence("E-CON-001", "Strošek: 79,6 mio EUR.", "Lani 12 %."), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_each_sentence_is_checked_against_the_evidence_it_cites(self):
        text = ("It costs EUR 80 million ([E-CON-001](../agent/evidence/E-CON-001.md)). Last year 12%, now 14% "
                "([E-CON-001](../agent/evidence/E-CON-001.md)).\n\nNobody says 99 here.\n"
                "| A 14% row | [E-CON-001](../agent/evidence/E-CON-001.md) |")
        self.assertEqual(numcheck.check_prose(text, "report.md", self.ev),
                         ["NUMBER report.md:1: 14 is in none of E-CON-001", "NUMBER report.md:4: 14 is in none of E-CON-001"])


class Calc(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        ev = self.folder / "evidence"
        ev.mkdir()
        (ev / "E-CON-001.md").write_text(evidence("E-CON-001", "Najvišja osnova znaša 5.159,12 eura."), encoding="utf-8")
        (ev / "E-PRO-004.md").write_text(evidence("E-PRO-004", "Stopnja za leto 2025 znaša 36,83 %."), encoding="utf-8")
        (ev / "E-PRO-005.md").write_text(evidence("E-PRO-005", "Znaša 99.", result="failed"), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_ev(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "evidence.py"), *args], capture_output=True, text=True)

    def calc(self, formula, eid="E-PRO-006"):
        return self.run_ev("calc", str(self.folder), formula, "--id", eid, "--added-by", "PRO", "--stage", "rebuttal",
                           "--title", "Gross wage at the cap", "--method", "Net base over one minus the rate.")

    def test_a_calc_is_written_recomputed_and_counted_as_citing(self):
        r = self.calc("E-CON-001:5159.12 / (1 - E-PRO-004:36.83 / 100)")
        self.assertEqual(r.returncode, 0, r.stderr)
        text = (self.folder / "evidence" / "E-PRO-006.md").read_text(encoding="utf-8")
        self.assertIn("> 5159.12 / (1 - 36.83 / 100) = 8167.04", text)
        self.assertIn("inputs: E-CON-001, E-PRO-004", text)
        self.assertIn("- 5159.12 from E-CON-001 (Quote: …Najvišja osnova znaša 5.159,12 eura.…)", text)
        self.assertIn("| E-PRO-006 | recomputed |", self.run_ev("verify", str(self.folder), "E-PRO-006").stdout)
        # the NUMBER check reads the calc's result, and its inputs
        self.assertEqual(numcheck.check_prose("About EUR 8,167 gross, from EUR 5,159.12 net (E-PRO-006).", "r.md",
                                              self.folder / "evidence"), [])
        # an edited result no longer recomputes
        (self.folder / "evidence" / "E-PRO-006.md").write_text(text.replace("result: 8167.04", "result: 8100"), encoding="utf-8")
        self.assertIn("differs: now 8167.04, file says 8100", self.run_ev("verify", str(self.folder), "E-PRO-006").stdout)
        # ledger.py: the calc cites its inputs
        (self.folder / "1-opening-pro.md").write_text("Cites E-PRO-006 and E-PRO-005.\n", encoding="utf-8")
        out = subprocess.run([sys.executable, str(SCRIPTS / "ledger.py"), str(self.folder)], capture_output=True, text=True).stdout
        self.assertNotIn("UNCITED", out)
        self.assertIn("| E-PRO-006 |", (self.folder / "ledger.md").read_text(encoding="utf-8").replace("[E-PRO-006](evidence/E-PRO-006.md)", "E-PRO-006"))

    def test_inputs_must_stand_in_their_evidence(self):
        self.assertIn("36.8 is not in the Quote or Context of E-PRO-004", self.calc("E-PRO-004:36.8 * 2").stderr)
        self.assertIn("E-PRO-009 does not exist", self.calc("E-PRO-009:1 + 1").stderr)
        self.assertIn("E-PRO-005 failed the Audit", self.calc("E-PRO-005:99 * 2").stderr)
        self.assertIn("uses no Evidence", self.calc("2 + 2").stderr)
        self.assertIn("only numbers", self.calc("E-PRO-004:36.83 + __import__('os').getpid()").stderr)
        self.assertFalse((self.folder / "evidence" / "E-PRO-006.md").exists())


class Figures(unittest.TestCase):
    """report_html.py checks each figure value against the Evidence it cites."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ev = self.root / "agent" / "evidence"
        self.ev.mkdir(parents=True)
        (self.root / "outputs").mkdir()
        (self.root / "agent" / "motion.md").write_text("# Motion\n\n**The act should pass.**\n", encoding="utf-8")
        (self.root / "outputs" / "report.md").write_text("# Debate Report: The act\n\n## 1. Motion\n\nText.\n", encoding="utf-8")
        (self.ev / "E-CON-001.md").write_text(evidence("E-CON-001", "Strošek: 79,6 mio EUR, lani 183 mio EUR."), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, *figures):
        (self.root / "agent" / "figures.json").write_text(json.dumps({"figures": list(figures)}), encoding="utf-8")
        r = subprocess.run([sys.executable, str(SCRIPTS / "report_html.py"), str(self.root)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [ln for ln in r.stdout.splitlines() if ln.startswith("FIGURE")]

    def test_a_bar_value_must_be_in_its_evidence(self):
        bar = {"id": "cost", "type": "bar", "title": "Cost", "unit": "EUR million", "categories": ["Now", "Then", "Never"],
               "series": [{"name": "Cost", "values": [80.0, 138, 0], "evidence": ["E-CON-001", "E-CON-001", "E-CON-001"]}]}
        self.assertEqual(self.build(bar), ["FIGURE cost: 138 is in none of E-CON-001"])  # a zero is not checked

    def test_line_points_are_checked_and_a_rate_may_be_a_share(self):
        (self.ev / "E-PRO-002.md").write_text(evidence("E-PRO-002", "Rate 36,83 %, share 0,25, base 17,9 tisoč EUR (Art. 64)."),
                                              encoding="utf-8")
        line = {"id": "rate", "type": "line", "title": "Rate", "unit": "share of the wage",
                "series": [{"name": "Rate", "points": [[2025, 0.3683], [2026, 0.41], [2027, 0.0025]], "evidence": "E-PRO-002"}]}
        pct = {"id": "pct", "type": "bar", "title": "Rate", "unit": "% of the wage", "categories": ["A", "B", "C"],
               "series": [{"name": "Rate", "values": [36.83, 25, 3683], "evidence": ["E-PRO-002"] * 3}]}
        # a scale word converts exactly; an amount is not a rate, so 6400 is not the "64" of Art. 64 times 100
        bar = {"id": "base", "type": "bar", "title": "Base", "unit": "EUR, corporate tax", "categories": ["Base", "Tax"],
               "series": [{"name": "Base", "values": [17900, 6400], "evidence": ["E-PRO-002", "E-PRO-002"]}]}
        self.assertEqual(self.build(line, pct, bar), ["FIGURE rate: 0.41 is in none of E-PRO-002",
                                                      "FIGURE rate: 0.0025 is in none of E-PRO-002",
                                                      "FIGURE pct: 3683 is in none of E-PRO-002",
                                                      "FIGURE base: 6400 is in none of E-PRO-002"])

    def test_a_computed_value_passes_through_a_calc_named_in_the_note_and_is_flagged_otherwise(self):
        for eid, found in (("E-CON-002", "yes"), ("E-CON-003", "no")):
            (self.ev / f"{eid}.md").write_text(
                f"---\nid: {eid}\nadded_by: CON\nkind: calc\ntitle: Sum\npublisher: evidence.py calc\n"
                f"url: evidence/{eid}.md\nresult: 262.6\n---\n\n## Quote\n\n> 79.6 + 183 + 12 = 262.6\n\n"
                f"## Audit\n\n- Quote found: {found}\n- Supports: yes\n- Cherry-picked: no\n- Source Tier: A\n",
                encoding="utf-8")
        fig = lambda fid, v, note: {"id": fid, "type": "bar", "title": "Total", "unit": "EUR million",  # noqa: E731
                                    "categories": ["Both"], **({"note": note} if note else {}),
                                    "series": [{"name": "Total", "values": [v], "evidence": ["E-CON-001"]}]}
        self.assertEqual(self.build(fig("calc", 263, "The sum of the two (E-CON-002)."),
                                    fig("input", 12, "The sum of the two (E-CON-002)."),  # only the calc's result counts
                                    fig("failed", 263, "The sum of the two (E-CON-003)."),
                                    fig("noted", 263, "Computed as the sum of the two."),
                                    fig("typo", 236, "Estimates from the ministry."),
                                    fig("bare", 236, "")),
                         ["FIGURE input: 12 is in none of E-CON-001",
                          "FIGURE failed: E-CON-003 in its note failed the Audit",
                          "FIGURE failed: 263 is in none of E-CON-001",
                          "FIGURE noted: 263 is computed (see its note), in none of E-CON-001; "
                          "name in note a calc that states it, or list this line in your reply",
                          "FIGURE typo: 236 is in none of E-CON-001",
                          "FIGURE bare: 236 is in none of E-CON-001"])


if __name__ == "__main__":
    unittest.main()
