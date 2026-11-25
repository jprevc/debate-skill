"""The Wayback Machine in evidence.py: verify --live falls back to an archived copy when a site is down,
fetch --archive caches the latest snapshot, and quote records a snapshot (Save Page Now) when EVIDENCE_ARCHIVE is on.
The archive is a fake: no test touches the network.

Run: uv run --with markdown==3.7 --with pytest==9.2.0 pytest tests
"""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "debate" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import evidence  # noqa: E402

URL = "https://fs-rs.si/porocilo.html"
PAGE = b"<html><body><p>Intro.</p><p>The total static effect is EUR 1,195 million in 2027.</p><p>End.</p></body></html>"
QUOTE = "The total static effect is EUR 1,195 million in 2027."
SNAPSHOT = f"http://web.archive.org/web/20260501083000/{URL}"


class FakeWeb:
    """The live site (up or down) and the Wayback Machine, behind evidence._get and evidence._save_page_now."""

    def __init__(self, site_up=True, archived=PAGE, saves=True):
        self.site_up, self.archived, self.saves, self.calls = site_up, archived, saves, []

    def get(self, url):
        self.calls.append(url)
        if url == URL:
            if not self.site_up:
                raise urllib.error.URLError("[Errno -2] Name or service not known")
            return PAGE, "text/html", False
        if url.startswith("https://archive.org/wayback/available?"):
            asked = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["url"][0]
            closest = {"available": True, "status": "200", "url": SNAPSHOT, "timestamp": "20260501083000"} \
                if self.archived and asked == URL else None
            return json.dumps({"url": asked, "archived_snapshots": {"closest": closest} if closest else {}}).encode(), \
                "application/json", False
        if re.fullmatch(rf"https://web\.archive\.org/web/\d{{14}}id_/{re.escape(URL)}", url) and self.archived:
            return self.archived, "text/html", False
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    def save(self, url):
        self.calls.append(f"save {url}")
        if not self.saves:
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
        return f"https://web.archive.org/web/20261125101500/{url}"

    def patch(self):
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(evidence, "_get", side_effect=self.get))
        stack.enter_context(mock.patch.object(evidence, "_save_page_now", side_effect=self.save))
        return stack


class Debate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "agent"
        (self.folder / "evidence").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, fn, web, **args):
        out = io.StringIO()
        with web.patch(), contextlib.redirect_stdout(out):
            fn(mock.Mock(folder=str(self.folder), **args))
        return out.getvalue()

    def fetch(self, web, archive=False):
        return self.run_cmd(evidence.cmd_fetch, web, url=URL, keywords=[], refresh=False, render=False,
                            archive=archive, max=8)

    def quote(self, web, source_file, eid="E-PRO-001"):
        self.out = self.run_cmd(evidence.cmd_quote, web, file=str(source_file), range="2-2", id=eid, added_by="PRO",
                     stage="opening", title="Analysis", author="unknown", publisher="Fiscal Council",
                     published="2026", language="en", start_at=None, end_after=None, context=1,
                     translation=None, url=None, force=False)
        return (self.folder / "evidence" / f"{eid}.md").read_text(encoding="utf-8")

    def verify(self, web):
        return self.run_cmd(evidence.cmd_verify, web, ids=[], live=True)

    def cached_file(self):
        return next((self.folder / "evidence" / "files" / "web").glob("*.txt"))


class VerifyFallsBackToTheArchive(Debate):
    def setUp(self):
        super().setUp()
        self.fetch(FakeWeb())
        self.quote(FakeWeb(), self.cached_file())

    def test_a_site_that_is_down_is_checked_against_its_latest_snapshot(self):
        out = self.verify(FakeWeb(site_up=False))
        self.assertIn("| E-PRO-001 | exact | archived 2026-05-01: exact |", out)
        self.assertIn(SNAPSHOT, out)

    def test_a_snapshot_without_the_quote_is_missing(self):
        out = self.verify(FakeWeb(site_up=False, archived=PAGE.replace(b"1,195", b"1,250")))
        self.assertIn("| E-PRO-001 | exact | archived 2026-05-01: missing |", out)

    def test_no_snapshot_leaves_it_unreachable(self):
        self.assertIn("| E-PRO-001 | exact | unreachable |", self.verify(FakeWeb(site_up=False, archived=None)))

    def test_a_site_that_is_up_is_not_looked_up_in_the_archive(self):
        web = FakeWeb()
        self.assertIn("| E-PRO-001 | exact | unchanged |", self.verify(web))
        self.assertEqual(web.calls, [URL])


class FetchArchive(Debate):
    def test_the_latest_snapshot_is_cached_with_its_url_and_date(self):
        out = self.fetch(FakeWeb(site_up=False), archive=True)
        self.assertIn("archived 2026-05-01", out)
        meta = json.loads(self.cached_file().with_suffix(".json").read_text(encoding="utf-8"))
        self.assertEqual((meta["url"], meta["archive_url"], meta["archived"]), (URL, SNAPSHOT, "2026-05-01"))
        self.assertTrue(self.cached_file().name.endswith("-archived.txt"))

    def test_evidence_quoted_from_a_snapshot_names_the_page_and_the_snapshot(self):
        self.fetch(FakeWeb(site_up=False), archive=True)
        text = self.quote(FakeWeb(), self.cached_file())
        self.assertIn(f"url: {URL}\n", text)
        self.assertIn(f"archive_url: {SNAPSHOT}\n", text)
        # the site is back, serving the bytes the snapshot kept
        self.assertIn("| E-PRO-001 | exact | unchanged |", self.verify(FakeWeb()))

    def test_a_site_that_is_down_is_checked_against_the_snapshot_the_evidence_names(self):
        self.fetch(FakeWeb())
        text = self.quote(FakeWeb(), self.cached_file()).replace(
            "---\n\n## Quote", f"archive_url: https://web.archive.org/web/20260301000000/{URL}\n---\n\n## Quote")
        (self.folder / "evidence" / "E-PRO-001.md").write_text(text, encoding="utf-8")
        web = FakeWeb(site_up=False)
        self.assertIn("| E-PRO-001 | exact | archived 2026-03-01: exact |", self.verify(web))
        self.assertEqual(web.calls, [URL, f"https://web.archive.org/web/20260301000000id_/{URL}"])

    def test_no_snapshot_fails_the_fetch(self):
        with self.assertRaises(SystemExit):
            out = self.fetch(FakeWeb(site_up=False, archived=None), archive=True)
        self.assertEqual(list((self.folder / "evidence").rglob("*.txt")), [])


class SnapshotOnQuote(Debate):
    def setUp(self):
        super().setUp()
        self.fetch(FakeWeb())

    def archive(self, web):
        with mock.patch.object(evidence.time, "sleep"):
            return self.run_cmd(evidence.cmd_archive, web)

    def test_off_by_default_nothing_is_sent_to_the_archive(self):
        web = FakeWeb()
        with mock.patch.dict(os.environ, {"EVIDENCE_ARCHIVE": ""}):
            text = self.quote(web, self.cached_file())
            self.assertNotIn("archive_url", text)
            self.assertEqual(web.calls, [])
            with self.assertRaises(SystemExit):
                self.archive(web)
        self.assertEqual(web.calls, [])

    def test_on_each_quoted_page_is_snapshot_once_and_recorded(self):
        web = FakeWeb()
        with mock.patch.dict(os.environ, {"EVIDENCE_ARCHIVE": "1"}):
            first = self.quote(web, self.cached_file(), "E-PRO-001")
            second = self.quote(web, self.cached_file(), "E-PRO-002")
        snap = f"archive_url: https://web.archive.org/web/20261125101500/{URL}\n"
        self.assertIn(snap, first)
        self.assertIn(snap, second)
        self.assertEqual(web.calls, [f"save {URL}"])

    def test_a_failed_snapshot_does_not_fail_the_quote_and_waits_for_archive(self):
        with mock.patch.dict(os.environ, {"EVIDENCE_ARCHIVE": "1"}):
            text = self.quote(FakeWeb(saves=False), self.cached_file())
            self.assertNotIn("archive_url", text)
            self.assertIn("evidence.py archive", self.out)
            out = self.archive(FakeWeb())
        self.assertIn("E-PRO-001", out)
        text = (self.folder / "evidence" / "E-PRO-001.md").read_text(encoding="utf-8")
        self.assertIn(f"archive_url: https://web.archive.org/web/20261125101500/{URL}\n---\n", text)
        self.assertIn("> The total static effect", text)


def test_the_html_report_links_the_snapshot_beside_the_source(tmp_path):
    from test_confrontation import Debate as FinishedDebate
    debate = FinishedDebate(tmp_path)
    p = debate.agent / "evidence" / "E-PRO-001.md"
    p.write_text(p.read_text(encoding="utf-8").replace("---\n\n## Quote", f"url: {URL}\narchive_url: {SNAPSHOT}\n---\n\n## Quote"),
                 encoding="utf-8")
    (debate.outputs / "report.md").write_text("# Should the act enter into force?\n\n## 1. Summary\n\n"
                                              "It pays for itself ([E-PRO-001](../agent/evidence/E-PRO-001.md)).\n",
                                              encoding="utf-8")
    page = debate.html()
    assert f'"archive_url": "{SNAPSHOT}"' in page
    assert "e.archive_url" in page and '"archived": "archived copy"' in page


if __name__ == "__main__":
    unittest.main()
