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
    h3 = body.index('<h3 id="dim-tax-bands">')
    lead = body.index('<p class="lede">The act replaces')
    fig = body.index(FIG)
    settled = body.index("<strong>Settled</strong>")
    assert h3 < lead < fig < settled


REPORT_WITHOUT_LEAD = REPORT_WITH_LEAD.replace(
    "The act replaces the flat 80% expense rate with three bands, per [E-PRIMARY-001](../agent/evidence/E-PRIMARY-001.md).\n\n", "")


def test_older_report_without_lead_keeps_figures_directly_under_the_heading():
    body = report_html.render_body(REPORT_WITHOUT_LEAD, {"Tax bands": [FIG]})
    assert f'<h3 id="dim-tax-bands">Tax bands</h3>{FIG}' in body
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
    assert lead_end < body.index(FIG) < body.index("<strong>Settled</strong>")


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
