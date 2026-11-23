"""ledger.py and a revised debate: Evidence that only an archived case file in agent/history/<N>/ cites
is still cited (the earlier Report links to it), and archived files are not checked as live case files.

Run: uv run --with markdown==3.7 --with pytest==9.2.0 pytest tests
"""
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "debate" / "scripts"
LEDGER = SCRIPTS / "ledger.py"
sys.path.insert(0, str(SCRIPTS))
import evidence  # noqa: E402
EV = "---\nadded_by: PRO\ntitle: t\npublisher: p\n---\n\n## Quote\n\nq\n"


class History(unittest.TestCase):
    def test_archived_citations_count_and_archived_files_are_not_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = Path(tmp) / "agent"
            (agent / "evidence").mkdir(parents=True)
            (agent / "history" / "1").mkdir(parents=True)
            (agent / "evidence" / "E-PRO-001.md").write_text(EV, encoding="utf-8")
            (agent / "evidence" / "E-PRO-002.md").write_text(EV, encoding="utf-8")
            # an archived rejoinder, missing every required section: it must not be checked
            (agent / "history" / "1" / "4-rejoinder-pro.md").write_text("cites E-PRO-002\n", encoding="utf-8")
            (agent / "1-opening-pro.md").write_text(
                "## Summary\n## Arguments the user has heard\n## Proposed Dimensions\n## Evidence Requests\n"
                "**PRO-1** · Dimension: Cost · Type: Factual · Evidence: E-PRO-001\nx\n", encoding="utf-8")
            out = subprocess.run([sys.executable, str(LEDGER), str(agent)], capture_output=True, text=True).stdout
            self.assertNotIn("UNCITED", out)
            self.assertNotIn("history", out.replace("ledger.md written", ""))
            self.assertIn("history/1/4-rejoinder-pro", (agent / "ledger.md").read_text(encoding="utf-8"))


class LiveVerify(unittest.TestCase):
    def test_a_source_many_evidence_quote_is_downloaded_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = Path(tmp)
            (agent / "evidence").mkdir()
            for n, q in (("001", "alpha beta"), ("002", "gamma delta")):
                (agent / "evidence" / f"E-PRO-{n}.md").write_text(
                    f"---\nurl: https://example.org/a\n---\n\n## Quote\n\n> {q}\n", encoding="utf-8")
            page = (b"<html><body><p>alpha beta</p><p>gamma delta</p></body></html>", "text/html", False)
            out = io.StringIO()
            with mock.patch.object(evidence, "_get", return_value=page) as get, contextlib.redirect_stdout(out):
                evidence.cmd_verify(mock.Mock(folder=str(agent), ids=[], live=True))
            self.assertEqual(get.call_count, 1)
            self.assertIn("| E-PRO-001 | — | exact |", out.getvalue())
            self.assertIn("| E-PRO-002 | — | exact |", out.getvalue())


if __name__ == "__main__":
    unittest.main()
