"""Building the HTML Report: the block of Evidence Requests the debate could not get.

Run: uv run --with markdown==3.7 python3 -m unittest discover tests
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "debate" / "scripts" / "report_html.py"

REPORT = "# Debate Report: test\n\n## 1. Motion and scope\n\nScope.\n\n## 2. Bottom line by Dimension\n\n### Cost\n\nText.\n"
HEADER = ("| ID | Priority | For | Status | Needed | Tried | Where | Effort | Fulfilled by |\n"
          "|---|---|---|---|---|---|---|---|---|\n")


def build(state_rows=None, language="English", lang=None):
    """Build a minimal debate folder and its HTML Report; return (page, printed output)."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "agent").mkdir()
        (root / "outputs").mkdir()
        (root / "agent" / "motion.md").write_text(f"**The bill should pass.**\n\nReport language: {language}\n", encoding="utf-8")
        if state_rows is not None:
            (root / "agent" / "state.md").write_text(
                f"# Debate state\n\n## Evidence Requests\n\n{HEADER}{state_rows}\n## Log\n", encoding="utf-8")
        (root / "outputs" / "report.md").write_text(REPORT, encoding="utf-8")
        args = [sys.executable, str(SCRIPT), str(root)] + (["--lang", lang] if lang else [])
        if lang:
            (root / "outputs" / f"report-{lang}.md").write_text(REPORT, encoding="utf-8")
        run = subprocess.run(args, capture_output=True, text=True, check=True)
        page = (root / "outputs" / f"report{'-' + lang if lang else ''}.html").read_text(encoding="utf-8")
        return page, run.stdout


ROWS = ("| R-CON-C-2 | critical | CON-C-4 | open | Ministry costing of Arts 27-36 "
        "| memorandum and Fiscal Council analysis searched, nothing found | ZDIJZ request to the Ministry "
        "| freedom-of-information request (weeks) | |\n"
        "| R-PRO-D-3 + R-CON-D-4 | nice-to-have | PRO-D-23 | partial | household incidence | SURS tables | stat.si | browser (minutes) "
        "| evidence/files/web/surs-table.txt. Still missing: energy spending by income quintile. |\n"
        "| R-PRO-B-2 | nice-to-have | PRO-B-5 | fulfilled | tax rate | | | | evidence/files/web/rate.txt |\n")


class RequestsBlock(unittest.TestCase):
    def test_unmet_requests_are_listed_on_the_glance_tab(self):
        page, out = build(ROWS)
        glance = page[page.index('id="panel-record"'):]
        block = glance[glance.index('id="requests"'):]
        for text in ("Evidence the debate could not get", "R-CON-C-2", "R-PRO-D-3", "R-CON-D-4", "CON-C-4",
                     "Ministry costing of Arts 27-36", "memorandum and Fiscal Council analysis searched, nothing found",
                     "ZDIJZ request to the Ministry", "freedom-of-information request (weeks)",
                     "energy spending by income quintile."):
            self.assertIn(text, block)
        self.assertLess(block.index("R-CON-C-2"), block.index("R-PRO-D-3"))  # open before partial
        self.assertNotIn("R-PRO-B-2", block)  # fulfilled
        self.assertNotIn("surs-table.txt", block)  # the cached path is not shown
        self.assertNotIn("REQUEST", out)

    def test_every_request_met_says_so(self):
        page, _ = build("| R-PRO-B-2 | nice-to-have | PRO-B-5 | fulfilled | tax rate | | | | evidence/files/web/rate.txt |\n")
        self.assertIn("Every Evidence Request was met.", page)

    def test_no_state_file_builds_without_the_block(self):
        page, out = build(None)
        self.assertNotIn('id="requests"', page)
        self.assertNotIn("REQUEST", out)

    def test_state_file_without_a_requests_table_builds_without_the_block(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "agent").mkdir()
            (root / "outputs").mkdir()
            (root / "agent" / "state.md").write_text("# Debate state\n\n## Log\n", encoding="utf-8")
            (root / "outputs" / "report.md").write_text(REPORT, encoding="utf-8")
            subprocess.run([sys.executable, str(SCRIPT), str(root)], capture_output=True, text=True, check=True)
            page = (root / "outputs" / "report.html").read_text(encoding="utf-8")
        self.assertNotIn('id="requests"', page)

    def test_unknown_status_prints_a_request_problem(self):
        _, out = build("| R-CON-A-9 | critical | CON-A-1 | waiting | x | | | | |\n")
        self.assertEqual([ln for ln in out.splitlines() if ln.startswith("REQUEST")],
                         ["REQUEST R-CON-A-9: status 'waiting' is not one of open, partial, fulfilled, unavailable; shown as open"])

    def test_slovenian_report_has_translated_labels(self):
        page, _ = build(ROWS, language="Slovenian")
        self.assertIn("Dokazi, ki jih razprava ni dobila", page)
        self.assertNotIn("Evidence the debate could not get", page)


if __name__ == "__main__":
    unittest.main()
