#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["markdown==3.7", "pytest==9.2.0"]
# ///
"""The Confrontation: the CONFRONTATION check in ledger.py and the Confrontation tab in report_html.py.

Each test builds a small finished debate folder, writes outputs/confrontation.md, and runs the
scripts as the orchestrator does. Run: uv run --script tests/test_confrontation.py
"""
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "debate" / "scripts"

MOTION = """\
# Motion

**The act should enter into force.**

- Report language: English

## Dimensions

1. **Cost**: what it costs.
2. **Legality**: whether it is lawful.

## Source Tiers for this domain

- A: the act itself
"""

CASES = {
    "1-opening-pro.md": """\
# Opening Case — PRO

## Cost

**PRO-1** · Dimension: Cost · Type: Factual · Evidence: E-PRO-001
The act is cheap.

**PRO-2** · Dimension: Cost · Type: Factual · Evidence: E-PRO-002
It pays for itself.

**PRO-4** · Dimension: Cost · Type: Value
Cost is not everything.

**PRO-5** · Dimension: Cost · Type: Value
The poor gain most.

## Legality

**PRO-3** · Dimension: Legality · Type: Value
It is fair.
""",
    "1-opening-con.md": """\
# Opening Case — CON

## Cost

**CON-1** · Dimension: Cost · Type: Factual · Evidence: E-CON-001, E-CON-002
The act is expensive.
""",
    "2-rebuttal-pro.md": """\
# Rebuttal — PRO

## Cost

**Re CON-1** · Rebut · Evidence: E-PRO-001
The estimate double counts.
""",
    "2-rebuttal-con.md": """\
# Rebuttal — CON

## Cost

**Re PRO-1** · Mitigate · Evidence: E-CON-001
Cheap now, not later.

**Re PRO-2** · Concede
No counter.

## Legality

**Re PRO-3** · Rebut
Fairness cuts the other way.
""",
}

EVIDENCE = {"E-PRO-001": ("PRO", "passed"), "E-PRO-002": ("PRO", "partial"),
            "E-CON-001": ("CON", "passed"), "E-CON-002": ("CON", "failed")}

GOOD = """\
# Should the act enter into force?

> An edited rendering of the written cases, not a real conversation.

## Cost

**Pro · Opening**
The act is cheap [E-PRO-001](../agent/evidence/E-PRO-001.md) and pays for itself [E-PRO-002](../agent/evidence/E-PRO-002.md).
(PRO-1, PRO-2; Not shown: PRO-4, PRO-5)

**Con · Opening**
It is expensive [E-CON-001](../agent/evidence/E-CON-001.md).
(CON-1)

**Pro · Rebuttal**
Con's estimate double counts [E-PRO-001](../agent/evidence/E-PRO-001.md).
(Re CON-1)

**Con · Rebuttal**
Con concedes: it pays for itself. But cheap now is not cheap later [E-CON-001](../agent/evidence/E-CON-001.md).
(Re PRO-2, Re PRO-1)

## Legality

**Pro · Opening**
It is fair.
(PRO-3)

**Con · Rebuttal**
Fairness cuts the other way.
(Re PRO-3)
"""


def evidence_file(eid, by, result):
    return textwrap.dedent(f"""\
        ---
        id: {eid}
        added_by: {by}
        title: Source of {eid}
        publisher: Someone
        ---

        ## Quote

        > A quote.

        ## Audit

        - Result: {result}{' — the context limits it to 2025' if result == 'partial' else ''}
        - Quote found: yes
        - Supports: yes
        - Cherry-picked: no
        - Source Tier: A
        - Funder/affiliation: n/a
        - Notes: none
        """)


class Debate:
    """A finished debate project folder in a temporary directory."""

    def __init__(self, root):
        self.root = root
        self.agent = self.root / "agent"
        self.outputs = self.root / "outputs"
        (self.agent / "evidence").mkdir(parents=True)
        self.outputs.mkdir()
        (self.agent / "motion.md").write_text(MOTION, encoding="utf-8")
        for name, text in CASES.items():
            (self.agent / name).write_text(text, encoding="utf-8")
        for eid, (by, result) in EVIDENCE.items():
            (self.agent / "evidence" / f"{eid}.md").write_text(evidence_file(eid, by, result), encoding="utf-8")
        (self.outputs / "report.md").write_text("# Should the act enter into force?\n\n## 1. Summary\n\nText.\n", encoding="utf-8")

    def confrontation(self, text, lang=None):
        (self.outputs / f"confrontation{'-' + lang if lang else ''}.md").write_text(text, encoding="utf-8")

    def ledger(self):
        out = subprocess.run([sys.executable, str(SCRIPTS / "ledger.py"), str(self.root)], capture_output=True, text=True, check=True).stdout
        return [ln for ln in out.splitlines() if ln.startswith("CONFRONTATION")]

    def html(self, lang=None):
        args = ["uv", "run", "--quiet", "--script", str(SCRIPTS / "report_html.py"), str(self.root)] + (["--lang", lang] if lang else [])
        subprocess.run(args, capture_output=True, text=True, check=True)
        return (self.outputs / f"report{'-' + lang if lang else ''}.html").read_text(encoding="utf-8")


@pytest.fixture
def debate(tmp_path):
    return Debate(tmp_path)


def problems_for(debate, text):
    debate.confrontation(text)
    return debate.ledger()


def has_problem(problems, *fragments):
    return any(all(f in p for f in fragments) for p in problems)


def test_a_faithful_confrontation_has_no_problems(debate):
    assert problems_for(debate, GOOD) == []


def test_a_turn_citing_the_other_sides_claim(debate):
    problems = problems_for(debate, GOOD.replace("(PRO-1, PRO-2;", "(PRO-1, PRO-2, CON-1;"))
    assert has_problem(problems, "Cost", "Pro Opening", "CON-1"), problems


def test_a_claim_left_out_of_both_lists(debate):
    problems = problems_for(debate, GOOD.replace("(PRO-1, PRO-2;", "(PRO-1;"))
    assert has_problem(problems, "Pro Opening", "PRO-2", "Not shown"), problems


def test_a_claim_under_not_shown_is_accounted_for(debate):
    text = GOOD.replace(" and pays for itself [E-PRO-002](../agent/evidence/E-PRO-002.md).", ".")
    assert problems_for(debate, text.replace("(PRO-1, PRO-2; Not shown:", "(PRO-1; Not shown: PRO-2,")) == []


def test_a_missing_turn(debate):
    con_opening = "**Con · Opening**\nIt is expensive [E-CON-001](../agent/evidence/E-CON-001.md).\n(CON-1)\n\n"
    assert con_opening in GOOD
    problems = problems_for(debate, GOOD.replace(con_opening, ""))
    assert has_problem(problems, "Cost", "no Con Opening turn", "CON-1"), problems


def test_evidence_that_failed_the_audit(debate):
    # CON-1 cites E-CON-002, but it failed the Audit
    problems = problems_for(debate, GOOD.replace("It is expensive [E-CON-001]", "It is expensive [E-CON-002](../agent/evidence/E-CON-002.md) [E-CON-001]"))
    assert has_problem(problems, "Con Opening", "E-CON-002", "failed"), problems


def test_evidence_the_paraphrased_items_do_not_cite(debate):
    # E-PRO-002 is cited by PRO-2, which the Pro Rebuttal turn does not paraphrase
    problems = problems_for(debate, GOOD.replace("double counts [E-PRO-001]", "double counts [E-PRO-002]"))
    assert has_problem(problems, "Pro Rebuttal", "E-PRO-002", "Re CON-1"), problems


def test_evidence_that_does_not_exist(debate):
    problems = problems_for(debate, GOOD.replace("double counts [E-PRO-001]", "double counts [E-PRO-009]"))
    assert has_problem(problems, "Pro Rebuttal", "E-PRO-009", "no Evidence file"), problems


def test_a_turn_paraphrasing_more_than_three_items(debate):
    problems = problems_for(debate, GOOD.replace("(PRO-1, PRO-2; Not shown: PRO-4, PRO-5)", "(PRO-1, PRO-2, PRO-4, PRO-5)"))
    assert has_problem(problems, "Pro Opening", "at most 3"), problems


def test_a_turn_without_its_id_line(debate):
    problems = problems_for(debate, GOOD.replace("[E-CON-001](../agent/evidence/E-CON-001.md).\n(CON-1)\n", "[E-CON-001](../agent/evidence/E-CON-001.md).\n"))
    assert has_problem(problems, "Con Opening", "ID line"), problems


def test_turns_out_of_record_order(debate):
    con_opening = "**Con · Opening**\nIt is expensive [E-CON-001](../agent/evidence/E-CON-001.md).\n(CON-1)\n\n"
    pro_rebuttal = "**Pro · Rebuttal**\nCon's estimate double counts [E-PRO-001](../agent/evidence/E-PRO-001.md).\n(Re CON-1)\n\n"
    swapped = GOOD.replace(con_opening + pro_rebuttal, pro_rebuttal + con_opening)
    assert swapped != GOOD
    assert has_problem(problems_for(debate, swapped), "Cost", "Con Opening", "order"), swapped


def test_a_section_that_is_not_a_dimension_and_a_dimension_without_a_section(debate):
    problems = problems_for(debate, GOOD.replace("## Legality", "## Lawfulness"))
    assert has_problem(problems, "Lawfulness", "not a Dimension in motion.md"), problems
    assert has_problem(problems, "Legality", "no section"), problems


def test_a_claim_restated_at_a_later_stage_belongs_to_that_stages_turn(debate):
    rebuttal = debate.agent / "2-rebuttal-pro.md"
    rebuttal.write_text(rebuttal.read_text(encoding="utf-8")
                        + "\n**PRO-1 (restated)** · Dimension: Cost · Type: Factual · Evidence: E-PRO-002\nStill cheap.\n", encoding="utf-8")
    assert has_problem(problems_for(debate, GOOD), "Pro Rebuttal", "PRO-1", "Not shown")
    restated = GOOD.replace("(Re CON-1)", "(Re CON-1, PRO-1)").replace("double counts [E-PRO-001](../agent/evidence/E-PRO-001.md).",
                                                                      "double counts [E-PRO-001](../agent/evidence/E-PRO-001.md); still cheap [E-PRO-002](../agent/evidence/E-PRO-002.md).")
    assert problems_for(debate, restated) == []


SLOVENIAN = (GOOD.replace("**Pro · ", "**Za · ").replace("**Con · ", "**Proti · ").replace("Opening**", "Uvodni nastop**")
             .replace("Rebuttal**", "Odgovor**").replace("Not shown", "Ni prikazano")
             .replace("## Cost", "## Stroški").replace("## Legality", "## Zakonitost"))


def test_a_translation_that_mirrors_the_original(debate):
    debate.confrontation(SLOVENIAN, lang="sl")
    assert problems_for(debate, GOOD) == []


def test_a_translation_that_drifts_from_the_original(debate):
    debate.confrontation(SLOVENIAN.replace("(Re CON-1)", "(Re CON-1, Re CON-9)"), lang="sl")
    problems = problems_for(debate, GOOD)
    assert has_problem(problems, "confrontation-sl.md", "Stroški", "Za · Odgovor", "does not mirror"), problems


def test_a_translation_with_a_missing_section(debate):
    debate.confrontation(SLOVENIAN[:SLOVENIAN.index("## Zakonitost")], lang="sl")
    problems = problems_for(debate, GOOD)
    assert has_problem(problems, "confrontation-sl.md", "1 sections", "confrontation.md has 2"), problems


def test_a_misspelled_turn_header(debate):
    problems = problems_for(debate, GOOD.replace("**Pro · Rebuttal**", "**Pro · Rebuttal:**"))
    assert has_problem(problems, "Pro · Rebuttal:", "not a turn header"), problems


def test_an_older_flat_folder_keeps_the_checkers_file_beside_the_confrontation(tmp_path):
    flat = Debate(tmp_path)
    for f in list(flat.agent.iterdir()) + list(flat.outputs.iterdir()):
        f.rename(tmp_path / f.name)
    flat.agent.rmdir(), flat.outputs.rmdir()
    flat.outputs = tmp_path
    flat.confrontation(GOOD)
    (tmp_path / "confrontation-check.md").write_text("## Round 1\n\n- No issues.\n", encoding="utf-8")
    assert flat.ledger() == []


# ---------- the Confrontation tab ----------

def test_the_tab_shows_each_dimension_as_bubbles_pro_left_con_right(debate):
    debate.confrontation(GOOD)
    page = debate.html()
    assert '<a href="#confrontation">Confrontation</a>' in page
    panel = page[page.index('id="panel-confrontation"'):]
    panel = panel[:panel.index('<div class="panel"') if '<div class="panel"' in panel else len(panel)]
    assert panel.index(">Cost</h3>") < panel.index(">Legality</h3>")
    assert panel.count('class="turn pro"') == 3 and panel.count('class="turn con"') == 3
    assert "not a real conversation" in panel
    assert 'data-ev="E-CON-001"' in panel
    assert "Not shown: PRO-4, PRO-5" in panel


def test_partial_evidence_carries_a_badge_with_the_auditors_result(debate):
    debate.confrontation(GOOD)
    page = debate.html()
    panel = page[page.index('id="panel-confrontation"'):]
    badge = panel[panel.index('data-ev="E-PRO-002"'):]
    badge = badge[:badge.index("</span>") + 7]
    assert 'class="flag"' in badge and ">partial<" in badge and "the context limits it to 2025" in badge, badge
    assert 'class="flag"' not in panel[panel.index('data-ev="E-PRO-001"'):panel.index('data-ev="E-PRO-002"')]


def test_no_tab_without_a_confrontation(debate):
    assert 'href="#confrontation"' not in debate.html()


def test_the_translated_report_shows_the_translated_confrontation(debate):
    (debate.outputs / "report-sl.md").write_text("# Ali naj zakon začne veljati?\n\n## 1. Povzetek\n\nBesedilo.\n", encoding="utf-8")
    debate.confrontation(GOOD)
    debate.confrontation(SLOVENIAN, lang="sl")
    page = debate.html("sl")
    assert '<a href="#confrontation">Soočenje</a>' in page
    assert ">Stroški</h3>" in page and "Za · Uvodni nastop" in page and "Ni prikazano" in page


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
