"""ledger.py on the command line: --help prints the usage, and a folder that isn't a debate is refused
before anything is written.

Run: uv run --with markdown==3.7 --with pytest==9.2.0 pytest tests
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "skills" / "debate" / "scripts" / "ledger.py"


def run(*args, cwd=None):
    return subprocess.run([sys.executable, str(LEDGER), *args], capture_output=True, text=True, cwd=cwd)


class Cli(unittest.TestCase):
    def test_help_prints_usage_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            for arg in ("--help", "-h"):
                r = run(arg, cwd=tmp)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("Usage: python3 ledger.py <debate-folder>", r.stdout)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_no_argument_prints_usage(self):
        r = run()
        self.assertEqual(r.returncode, 2)
        self.assertIn("Usage:", r.stderr)

    def test_a_folder_without_evidence_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run(tmp)
            self.assertEqual(r.returncode, 2)
            self.assertIn("not a debate folder", r.stderr)
            self.assertFalse((Path(tmp) / "ledger.md").exists())


if __name__ == "__main__":
    unittest.main()
