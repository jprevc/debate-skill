"""verify --live: a live download byte-identical to the cached one is `unchanged`, not text-matched again.

Run: uv run --with markdown==3.7 --with pytest==9.2.0 pytest tests
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "debate" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import evidence  # noqa: E402

URL = "https://example.org/analysis.html"
PAGE = b"<html><body><p>The total static effect is EUR 1,195 million in 2027.</p></body></html>"


class VerifyUnchanged(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "agent"
        (self.folder / "evidence").mkdir(parents=True)
        with mock.patch.object(evidence, "_get", return_value=(PAGE, "text/html", False)):
            txt, _ = evidence.fetch_to_cache(self.folder, URL)
        rel = txt.relative_to(self.folder)
        (self.folder / "evidence" / "E-PRO-001.md").write_text(
            f"---\nid: E-PRO-001\nurl: {URL}\nsource_file: {rel}\n---\n\n## Quote\n\n"
            "> The total static effect is EUR 1,195 million in 2027.\n\n## Audit\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def verify(self, live_bytes):
        out = io.StringIO()
        with mock.patch.object(evidence, "_get", return_value=(live_bytes, "text/html", False)), \
                contextlib.redirect_stdout(out):
            evidence.cmd_verify(mock.Mock(folder=str(self.folder), ids=[], live=True))
        return out.getvalue()

    def test_same_bytes_are_unchanged(self):
        self.assertIn("| E-PRO-001 | exact | unchanged |", self.verify(PAGE))

    def test_changed_bytes_are_text_matched(self):
        self.assertIn("| E-PRO-001 | exact | exact |", self.verify(PAGE.replace(b"<body>", b"<body><p>New.</p>")))
        self.assertIn("| E-PRO-001 | exact | missing |", self.verify(PAGE.replace(b"1,195", b"1,250")))


if __name__ == "__main__":
    unittest.main()
