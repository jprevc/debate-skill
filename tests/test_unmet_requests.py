"""The Evidence Requests table in state.md, read into the unmet requests the HTML Report lists.

Run: uv run --with markdown==3.7 python3 -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "debate" / "scripts"))
import report_html  # noqa: E402

HEADER = ("| ID | Priority | For | Status | Needed | Tried | Where | Effort | Fulfilled by |\n"
          "|---|---|---|---|---|---|---|---|---|\n")


def state(rows, header=HEADER):
    return f"# Debate state\n\n## Evidence Requests\n\n{header}{rows}\n<!-- comment -->\n\n## Log\n\n- something\n"


class UnmetRequests(unittest.TestCase):
    def setUp(self):
        report_html.problems.clear()

    def test_open_request_is_listed_with_every_field(self):
        text = state("| R-CON-C-2 | nice-to-have | CON-C-4, CON-C-3 | open | Ministry costing of Arts 27-36 "
                     "| not in the bill materials; memorandum, Fiscal Council analysis (keyword search) "
                     "| ZDIJZ request to the Ministry of Health | freedom-of-information request (weeks) | |\n")
        [r] = report_html.unmet_requests(text)
        self.assertEqual(r["ids"], ["R-CON-C-2"])
        self.assertEqual(r["priority"], "nice-to-have")
        self.assertEqual(r["for"], "CON-C-4, CON-C-3")
        self.assertEqual(r["status"], "open")
        self.assertEqual(r["needed"], "Ministry costing of Arts 27-36")
        self.assertEqual(r["tried"], "not in the bill materials; memorandum, Fiscal Council analysis (keyword search)")
        self.assertEqual(r["where"], "ZDIJZ request to the Ministry of Health")
        self.assertEqual(r["effort"], "freedom-of-information request (weeks)")
        self.assertEqual(r["missing"], "")
        self.assertEqual(report_html.problems, [])

    def test_fulfilled_requests_are_left_out(self):
        text = state("| R-PRO-B-2 | nice-to-have | PRO-B-5 | fulfilled | rate | | | | evidence/files/web/a.txt |\n"
                     "| R-CON-A-2 | nice-to-have | CON-A-12 | open | split | | | | |\n")
        self.assertEqual([r["ids"] for r in report_html.unmet_requests(text)], [["R-CON-A-2"]])

    def test_partial_request_shows_what_is_still_missing(self):
        text = state("| R-PRO-D-3 | nice-to-have | PRO-D-23 | partial | incidence | | | "
                     "| evidence/files/web/surs.txt (SURS table). Still missing: energy spending by quintile. |\n")
        [r] = report_html.unmet_requests(text)
        self.assertEqual(r["status"], "partial")
        self.assertEqual(r["missing"], "energy spending by quintile.")

    def test_old_fulfilled_partial_spelling_reads_as_partial(self):
        text = state("| R-PRO-A-2 | nice-to-have | PRO-A-16 | fulfilled (partial; recorded in Stage 2) | pass-through "
                     "| | | | evidence/files/web/gov.txt (VAT effect not separated). |\n")
        [r] = report_html.unmet_requests(text)
        self.assertEqual(r["status"], "partial")
        self.assertEqual(r["missing"], "")
        self.assertEqual(report_html.problems, [])

    def test_merged_request_lists_every_id(self):
        text = state("| R-PRO-B-1 + R-CON-B-2 | nice-to-have | PRO-B-10 | open | count | | | | |\n"
                     "| R-PRO-A-1 + R-CON-D-1 + R-PRO-D-2 (merged) | nice-to-have | PRO-A-3 | open | filers | | | | |\n")
        self.assertEqual([r["ids"] for r in report_html.unmet_requests(text)],
                         [["R-PRO-B-1", "R-CON-B-2"], ["R-PRO-A-1", "R-CON-D-1", "R-PRO-D-2"]])

    def test_unknown_status_is_shown_as_open_with_a_problem_line(self):
        text = state("| R-CON-A-9 | critical | CON-A-1 | waiting | x | | | | |\n")
        [r] = report_html.unmet_requests(text)
        self.assertEqual(r["status"], "open")
        self.assertEqual(len(report_html.problems), 1)
        self.assertTrue(report_html.problems[0].startswith("REQUEST R-CON-A-9"))

    def test_listed_by_status_then_critical_first(self):
        text = state("| R-1 | nice-to-have | P-1 | partial | a | | | | |\n"
                     "| R-2 | nice-to-have | P-2 | open | b | | | | |\n"
                     "| R-3 | critical | P-3 | unavailable | c | | | | |\n"
                     "| R-4 | critical | P-4 | partial | d | | | | |\n"
                     "| R-5 | critical | P-5 | open | e | | | | |\n")
        self.assertEqual([r["ids"][0] for r in report_html.unmet_requests(text)], ["R-5", "R-2", "R-3", "R-4", "R-1"])

    def test_old_table_without_the_new_columns_still_reads(self):
        old = "| ID | Priority | For | Status | Fulfilled by |\n|---|---|---|---|---|\n"
        text = state("| R-CON-A-2 | nice-to-have | CON-A-12 | open | |\n", header=old)
        [r] = report_html.unmet_requests(text)
        self.assertEqual((r["ids"], r["for"], r["status"]), (["R-CON-A-2"], "CON-A-12", "open"))
        self.assertEqual((r["needed"], r["tried"], r["where"], r["effort"]), ("", "", "", ""))

    def test_no_table_is_not_the_same_as_every_request_met(self):
        self.assertIsNone(report_html.unmet_requests("# Debate state\n\n## Log\n"))
        self.assertEqual(report_html.unmet_requests(state("")), [])

    def test_status_is_read_by_its_leading_word_in_any_case(self):
        text = state("| R-1 | nice-to-have | P-1 | Fulfilled | a | | | | e.txt |\n"
                     "| R-2 | critical | P-2 | unavailable (user declined) | b | | | | |\n"
                     "| R-3 | nice-to-have | P-3 | Partial | c | | | | |\n")
        self.assertEqual([(r["ids"][0], r["status"]) for r in report_html.unmet_requests(text)],
                         [("R-2", "unavailable"), ("R-3", "partial")])
        self.assertEqual(report_html.problems, [])


if __name__ == "__main__":
    unittest.main()
