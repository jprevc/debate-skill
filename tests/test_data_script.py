"""evidence.py data: a pinned statistics script, run with uv, cached as one row per line and re-run by verify.

Run: uv run --with markdown==3.7 --with pytest==9.2.0 pytest tests
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "debate" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import evidence  # noqa: E402

HEAD = '# /// script\n# requires-python = ">=3.12"\n# dependencies = [{deps}]\n# ///\n'
BODY = ('import json\n'
        'rows = [{"geo": "SI", "year": 2023, "value": 3.7}, {"geo": "SI", "year": 2024, "value": 3.0}]\n'
        'print("chatter from a library")\n'
        'print(json.dumps({"title": "Unemployment", "url": "https://example.org/une", "rows": rows}))\n')


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "evidence.py"), *args], capture_output=True, text=True)


class DataScript(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "agent"
        (self.folder / "evidence").mkdir(parents=True)
        self.script = Path(self.tmp.name) / "une-si.py"

    def tearDown(self):
        self.tmp.cleanup()

    def test_rows_are_cached_one_per_line_and_quoted_and_verified(self):
        self.script.write_text(HEAD.format(deps="") + BODY, encoding="utf-8")
        r = run("data", str(self.folder), str(self.script))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        cached = self.folder / "evidence" / "files" / "data" / "une-si.txt"
        self.assertEqual(cached.read_text(encoding="utf-8").splitlines(),
                         ["geo | year | value", "geo: SI | year: 2023 | value: 3.7", "geo: SI | year: 2024 | value: 3"])
        self.assertTrue(cached.with_suffix(".py").exists())
        r = run("quote", str(self.folder), str(cached), "2-2", "--id", "E-PRO-001", "--added-by", "PRO",
                "--stage", "opening", "--title", "t", "--publisher", "p", "--language", "en")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("url: https://example.org/une", (self.folder / "evidence" / "E-PRO-001.md").read_text())
        r = run("verify", str(self.folder), "--live")
        self.assertIn("| E-PRO-001 | exact | exact | re-ran script |", r.stdout)

    def test_a_loose_pin_is_refused(self):
        self.script.write_text(HEAD.format(deps='"sistat>=0.2"') + BODY, encoding="utf-8")
        r = run("data", str(self.folder), str(self.script))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("pin every dependency", r.stdout + r.stderr)

    def test_output_without_a_url_is_refused(self):
        self.script.write_text(HEAD.format(deps="") + BODY.replace('"url": "https://example.org/une", ', ""),
                               encoding="utf-8")
        r = run("data", str(self.folder), str(self.script))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("'url'", r.stdout)

    def test_dependencies_are_read_from_the_script_block(self):
        self.assertEqual(evidence._script_deps(HEAD.format(deps='"sistat==0.2.0", "pandas==2.3.3"')),
                         ["sistat==0.2.0", "pandas==2.3.3"])
        self.assertIsNone(evidence._script_deps("import json\n"))

    def test_missing_values_are_empty_and_columns_unioned(self):
        self.assertEqual(evidence._data_rows([{"a": 1.0, "b": float("nan")}, {"a": 2.5, "c": None}]),
                         ["a | b | c", "a: 1 | b:  | c: ", "a: 2.5 | b:  | c: "])


if __name__ == "__main__":
    unittest.main()
