#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["markdown==3.7", "pytest==9.2.0"]
# ///
"""Tests for skills/debate/scripts/report_html.py. Run: uv run --script tests/test_report_html.py"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills/debate/scripts"))
import report_html  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_state():
    report_html.problems.clear()
    report_html.UI = report_html.STRINGS["en"]
    yield
    report_html.problems.clear()
    report_html.UI = report_html.STRINGS["en"]


def report(settled, open_q, value_q, items):
    """A minimal Report whose one Dimension uses the given block labels."""
    s, o, v = items
    return (
        "# Report\n\n## 1. The Motion\n\ntext\n\n## 2. Bottom line by Dimension\n\n### Public finances\n\n"
        f"**{settled}**:\n\n" + "".join(f"- {b}\n" for b in s) + "\n"
        f"**{open_q}**:\n\n" + "".join(f"- {b}\n" for b in o) + "\n"
        f"**{value_q}**:\n\n" + "".join(f"- {b}\n" for b in v) + "\n"
        "## 3. Strength of each case\n\n| | Pro | Con |\n"
    )


EN_ITEMS = (
    ["Fact one", "Fact two"],
    ["**Does it cost more?** · Status: leaning Pro — the estimate shows", "**Is it legal?** · Status: unsettled — no ruling"],
    ["If you weigh speed over oversight, the Evidence favors Pro, because …"],
)
SL_ITEMS = (
    ["Dejstvo ena", "Dejstvo dve"],
    ["**Ali stane več?** · Stanje: v prid strani Za — ocena kaže", "**Ali je zakonito?** · Stanje: nerazrešeno — ni sodbe"],
    ["Če dajete prednost hitrosti pred nadzorom, dokazi govorijo v prid strani Za, ker …"],
)
EXPECTED = [{"dim": "Public finances", "settled": 2, "factual": ["leaning Pro", "unsettled"], "value": 1}]


@pytest.mark.parametrize("labels,items", [
    (("Settled", "Open questions", "Depends on your values"), EN_ITEMS),
    (("Ugotovljeno", "Odprta vprašanja", "Odvisno od vaših vrednot"), SL_ITEMS),
    (("Settled", "Factual Cruxes", "Value Cruxes"), EN_ITEMS),
    (("Ugotovljeno", "Dejstvena ključna vprašanja", "Vrednostna ključna vprašanja"), SL_ITEMS),
], ids=["new-en", "new-sl", "legacy-en", "legacy-sl"])
def test_crux_map_reads_new_and_legacy_labels(labels, items):
    assert report_html.crux_map(report(*labels, items)) == EXPECTED
    assert report_html.problems == []


def test_open_question_without_status_is_a_problem():
    text = report("Settled", "Open questions", "Depends on your values", (["Fact"], ["**Unmarked?** — no status"], []))
    report_html.crux_map(text)
    assert report_html.problems == ["STATUS Public finances: Open Question without '· Status: …' — **Unmarked?** — no status"]


@pytest.mark.parametrize("lang,headers,tooltip", [
    ("en", ["Open questions", "Depends on your values"], "value question"),
    ("sl", ["Odprta vprašanja", "Odvisno od vaših vrednot"], "vrednostno vprašanje"),
])
def test_crux_map_html_uses_new_wording(lang, headers, tooltip):
    report_html.UI = report_html.STRINGS[lang]
    out = report_html.record_charts({}, {}, {"PRO": 0, "CON": 0}, EXPECTED, {})
    for h in headers:
        assert f"<th>{h}</th>" in out
    assert f'data-tip="{tooltip}"' in out
    for old in ("Factual Cruxes", "Value Cruxes", "Dejstvena ključna", "Vrednostna ključna", "value crux"):
        assert old not in out


FIG = '<figure class="fig">CHART</figure>'

REPORT_WITH_LEAD = """# Debate Report: Should the act enter into force?

## 1. Motion and scope

The Motion.

## 2. Bottom line by Dimension

### Tax bands

The act replaces the flat 80% expense rate with three bands, per [E-PRIMARY-001](../agent/evidence/E-PRIMARY-001.md).

**Settled**:

- One settled fact.

**Factual Cruxes**:

- **Does it cost more?** · Status: leaning Con — the estimates differ.

**Value Cruxes**:

- If you weigh simplicity over fairness, the Evidence favors Con, because …

## 3. Strength of each case

Text.
"""


def test_lead_paragraph_is_marked_and_sits_above_the_dimensions_figures():
    body = report_html.render_body(REPORT_WITH_LEAD, {"Tax bands": [FIG]})
    h3 = body.index('<section class="dim" id="dim-tax-bands"><h3>')
    lead = body.index('<p class="lede">The act replaces')
    fig = body.index(FIG)
    settled = body.index('<strong class="blabel">Settled</strong>')
    assert h3 < lead < fig < settled


REPORT_WITHOUT_LEAD = REPORT_WITH_LEAD.replace(
    "The act replaces the flat 80% expense rate with three bands, per [E-PRIMARY-001](../agent/evidence/E-PRIMARY-001.md).\n\n", "")


def test_older_report_without_lead_keeps_figures_directly_under_the_heading():
    body = report_html.render_body(REPORT_WITHOUT_LEAD, {"Tax bands": [FIG]})
    assert f'<span class="dnum">2.1</span> Tax bands</h3>{FIG}' in body
    assert 'class="lede"' not in body


SLOVENIAN_DIMENSION = """## 2. Spodnja črta po dimenzijah

### Davčni razredi

**Ugotovljeno**:

- Eno dejstvo.
"""


def test_lead_paragraph_without_a_blank_line_before_settled_still_stays_apart_from_the_label():
    report = REPORT_WITH_LEAD.replace("E-PRIMARY-001.md).\n\n**Settled**", "E-PRIMARY-001.md).\n**Settled**")
    body = report_html.render_body(report, {"Tax bands": [FIG]})
    lead_end = body.index("</p>", body.index('<p class="lede">'))
    assert lead_end < body.index(FIG) < body.index('<strong class="blabel">Settled</strong>')


def test_a_slovenian_label_is_never_taken_for_a_lead_paragraph():
    body = report_html.render_body(SLOVENIAN_DIMENSION, {})
    assert 'class="lede"' not in body


def test_paragraphs_outside_section_2_are_not_lead_paragraphs():
    report = REPORT_WITH_LEAD + "\n### A subheading in section 3\n\nPlain text.\n"
    body = report_html.render_body(report, {})
    assert body.count('class="lede"') == 1


def test_lead_paragraph_does_not_change_crux_counts_or_raise_problems():
    report_html.problems.clear()
    expected = [{"dim": "Tax bands", "settled": 1, "factual": ["leaning Con"], "value": 1}]
    assert report_html.crux_map(REPORT_WITH_LEAD) == expected
    assert report_html.crux_map(REPORT_WITHOUT_LEAD) == expected
    assert report_html.problems == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
