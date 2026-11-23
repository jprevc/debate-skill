"""evidence.py papers: how an OpenAlex work is labelled for the Advocate and the Auditor.

Run: uv run --with markdown==3.7 --with pytest==9.2.0 pytest tests
"""
import os
import subprocess
import sys
import unittest
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

    def test_a_set_key_gives_no_warning(self):
        self.assertEqual(self.check("k").stdout, "OPENALEX_API_KEY is set.\n")


if __name__ == "__main__":
    unittest.main()
