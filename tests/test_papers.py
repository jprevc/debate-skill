"""evidence.py papers: how an OpenAlex work is labelled for the Advocate and the Auditor.

Run: uv run --with markdown==3.7 --with pytest==9.2.0 pytest tests
"""
import contextlib
import email.message
import io
import json
import os
import subprocess
import sys
import unittest
import urllib.error
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "debate" / "scripts"))
import evidence  # noqa: E402


def work(type_="article", venue_type="journal", retracted=False, locations=()):
    return {"type": type_, "is_retracted": retracted,
            "primary_location": {"source": {"type": venue_type}}, "locations": list(locations)}


def loc(url, version, oa=True, venue_type="repository", pdf=None):
    return {"landing_page_url": url, "pdf_url": pdf, "version": version, "is_oa": oa, "source": {"type": venue_type}}


class Papers(unittest.TestCase):
    def test_journal_article_and_review_keep_their_type(self):
        self.assertEqual(evidence._work_kind(work()), "article")
        self.assertEqual(evidence._work_kind(work("review")), "review")

    def test_an_article_in_a_repository_is_a_preprint(self):
        self.assertEqual(evidence._work_kind(work(venue_type="repository")), "preprint")

    def test_retraction_is_shown(self):
        self.assertEqual(evidence._work_kind(work(retracted=True)), "article · RETRACTED")

    def test_copies_prefer_the_pdf_link_and_drop_duplicates(self):
        w = work(locations=[loc("https://doi.org/10.1/x", "publishedVersion", oa=False, venue_type="journal"),
                            loc("https://ssrn.com/x", "submittedVersion", pdf="https://ssrn.com/x.pdf"),
                            loc("https://doi.org/10.1/x", "publishedVersion")])
        self.assertEqual(evidence._copies(w), [("https://doi.org/10.1/x", "publishedVersion", "journal", "closed"),
                                               ("https://ssrn.com/x.pdf", "submittedVersion", "repository", "open")])

    def test_abstract_is_rebuilt_from_the_inverted_index(self):
        w = {"abstract_inverted_index": {"wages": [1], "Minimum": [0], "rose": [2], "and": [3], "fell": [5], "jobs": [4]}}
        self.assertEqual(evidence._abstract(w), "Minimum wages rose and jobs fell")

    def check(self, key):
        env = {k: v for k, v in os.environ.items() if k != "OPENALEX_API_KEY"} | ({"OPENALEX_API_KEY": key} if key else {})
        return subprocess.run([sys.executable, evidence.__file__, "papers", "--check"],
                              capture_output=True, text=True, env=env)

    def test_a_missing_key_is_a_warning(self):
        r = self.check(None)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.startswith("WARNING: OPENALEX_API_KEY is not set"))



def http429(reason, reset="7200"):
    headers = email.message.Message()
    headers["Retry-After"] = "0"
    headers["X-RateLimit-Reset"] = reset
    return urllib.error.HTTPError("https://api.openalex.org/works", 429, "Too Many Requests", headers,
                                  io.BytesIO(json.dumps({"reason": reason}).encode()))


class Reply:
    def __init__(self, body, headers):
        self.body, self.headers = json.dumps(body).encode(), headers

    def read(self, _):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


SEARCH = {"meta": {"count": 0}, "results": []}


def papers(*argv, key="k"):
    """Run papers with OpenAlex mocked; return (stdout, exit code)."""
    a = mock.Mock(words=list(argv), check=False, since=None, reviews=False, open=False, max=1)
    out, code = io.StringIO(), 0
    env = {"OPENALEX_API_KEY": key} if key else {}
    with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(out):
        try:
            evidence.cmd_papers(a)
        except SystemExit as e:
            code = e.code
    return out.getvalue(), code


class Budget(unittest.TestCase):
    def setUp(self):
        evidence._budget.clear()

    def test_a_spent_budget_is_a_warning_with_the_reset_time(self):
        with mock.patch("urllib.request.urlopen", side_effect=http429("daily_budget")):
            out, code = papers("rent", "control")
        self.assertEqual(code, 1)
        self.assertIn("WARNING: OpenAlex budget used up: this key's daily budget is spent; it resets in about 2 h.", out)

    def test_without_a_key_the_spent_budget_points_to_a_key(self):
        with mock.patch("urllib.request.urlopen", side_effect=http429("daily_budget")):
            out, _ = papers("rent", key=None)
        self.assertIn("shared daily budget for this network is spent", out)
        self.assertIn("https://openalex.org/settings/api", out)

    def test_a_per_second_limit_is_retried(self):
        ok = Reply(SEARCH, {"X-RateLimit-Remaining": "9000", "X-RateLimit-Limit": "10000"})
        with mock.patch("urllib.request.urlopen", side_effect=[http429("requests_per_second"), ok]) as m:
            out, code = papers("rent")
        self.assertEqual((code, m.call_count), (0, 2))
        self.assertNotIn("WARNING", out)

    def test_a_low_budget_is_a_warning(self):
        low = Reply(SEARCH, {"X-RateLimit-Remaining": "500", "X-RateLimit-Limit": "10000",
                             "X-RateLimit-Credits-Used": "10", "X-RateLimit-Reset": "3600"})
        with mock.patch("urllib.request.urlopen", return_value=low):
            out, _ = papers("rent")
        self.assertIn("WARNING: OpenAlex budget low: this key's budget has about 50 searches left today; "
                      "it resets in about 1 h.", out)


    def test_check_with_a_key_reports_the_budget_left(self):
        rl = Reply({"rate_limit": {"daily_remaining_usd": 0.75, "daily_budget_usd": 1, "resets_in_seconds": 36000}}, {})
        a = mock.Mock(words=[], check=True)
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"OPENALEX_API_KEY": "k"}, clear=True), \
                mock.patch("urllib.request.urlopen", return_value=rl), contextlib.redirect_stdout(out):
            evidence.cmd_papers(a)
        self.assertEqual(out.getvalue(), "OPENALEX_API_KEY is set: 75% of today's budget left, about 750 searches; "
                                         "it resets in about 10 h.\n")


if __name__ == "__main__":
    unittest.main()
