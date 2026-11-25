"""ledger.py and the Judge's figures: a figure in figures.json (or figures-<lang>.json) cites the calc its note names
and the Evidence its series plot, so the ledger's "Cited in" names the figure and the calc is not UNCITED.

Run: uv run --with markdown==3.7 --with pytest==9.2.0 pytest tests
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "skills" / "debate" / "scripts" / "ledger.py"
EV = "---\nadded_by: {by}\ntitle: t\npublisher: p\n{extra}---\n\n## Quote\n\nq\n"


def row(ledger, eid):
    return next(ln for ln in ledger.splitlines() if ln.startswith(f"| [{eid}]"))


class Figures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.agent = Path(self.tmp.name) / "agent"
        ev = self.agent / "evidence"
        ev.mkdir(parents=True)
        (ev / "E-PRO-001.md").write_text(EV.format(by="PRO", extra=""), encoding="utf-8")
        (ev / "E-CON-002.md").write_text(EV.format(by="CON", extra=""), encoding="utf-8")
        (ev / "E-PRIMARY-004.md").write_text(
            EV.format(by="PRIMARY", extra="kind: calc\ninputs: E-PRO-001\nstage: finish\n"), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def figures(self, name, *figs):
        (self.agent / name).write_text(json.dumps({"figures": list(figs)}), encoding="utf-8")

    def ledger(self):
        out = subprocess.run([sys.executable, str(LEDGER), str(self.agent)], capture_output=True, text=True).stdout
        return out, (self.agent / "ledger.md").read_text(encoding="utf-8")

    def test_a_figure_cites_the_calc_its_note_names_and_the_evidence_its_series_plot(self):
        self.figures("figures.json", {
            "id": "cap-thresholds", "title": "T", "type": "bar", "categories": ["a", "b"], "note": "Calc: E-PRIMARY-004.",
            "series": [{"name": "s", "values": [1, 2], "evidence": [["E-PRIMARY-004"], "E-CON-002"]}]})
        out, ledger = self.ledger()
        self.assertTrue(row(ledger, "E-PRIMARY-004").endswith("| figure cap-thresholds |"), row(ledger, "E-PRIMARY-004"))
        self.assertTrue(row(ledger, "E-CON-002").endswith("| figure cap-thresholds |"), row(ledger, "E-CON-002"))
        self.assertTrue(row(ledger, "E-PRO-001").endswith("| E-PRIMARY-004 |"), row(ledger, "E-PRO-001"))
        self.assertNotIn("UNCITED", out)

    def test_a_translated_figures_file_cites_too(self):
        self.figures("figures-sl.json", {
            "id": "rast", "title": "T", "type": "line", "note": "Izračun: E-PRIMARY-004.",
            "series": [{"name": "s", "points": [[2025, 1]], "evidence": "E-CON-002"}]})
        out, ledger = self.ledger()
        self.assertTrue(row(ledger, "E-PRIMARY-004").endswith("| figure rast |"), row(ledger, "E-PRIMARY-004"))
        self.assertTrue(row(ledger, "E-CON-002").endswith("| figure rast |"), row(ledger, "E-CON-002"))


if __name__ == "__main__":
    unittest.main()
