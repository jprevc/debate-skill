#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["markdown==3.7", "pytest==9.2.0"]
# ///
"""Section 2 of the HTML Report: each Dimension is a numbered card, with a jump list and small block labels.
Run: uv run --script tests/test_report_dimension_cards.py"""
import re
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


REPORT = """# Debate Report: Should the act enter into force?

## 1. Motion and scope

The Motion. **Settled**: a label word in section 1.

## 2. Bottom line by Dimension

### Tax bands

The act replaces the flat rate with three bands.

**Settled**:

- One settled fact.

**Open questions**:

- **Does it cost more?** · Status: leaning Con — the estimates differ.

**Depends on your values**:

- If you weigh simplicity over fairness, the Evidence favors Con, because …

### VAT on energy

**Settled**:

- Another fact.

## 3. Strength of each case

**Settled**: a label in section 3.
"""


def section2(body):
    return re.search(r"<h2>2\..*?(?=<h2>|\Z)", body, re.S).group(0)


def test_each_dimension_is_a_numbered_card_holding_its_heading_lead_figures_and_blocks():
    fig = '<figure class="fig">CHART</figure>'
    body = report_html.render_body(REPORT, {"Tax bands": [fig]})
    cards = re.findall(r'<section class="dim" id="([^"]+)">(.*?)</section>', body, re.S)
    assert [c[0] for c in cards] == ["dim-tax-bands", "dim-vat-on-energy"]
    first, second = cards[0][1], cards[1][1]
    assert re.search(r'<h3><span class="dnum">2\.1</span> Tax bands</h3>', first)
    assert re.search(r'<h3><span class="dnum">2\.2</span> VAT on energy</h3>', second)
    assert first.index('<p class="lede">The act replaces') < first.index(fig) < first.index("One settled fact") < first.index("simplicity")
    assert "Another fact" in second and "Another fact" not in first


def test_section_2_opens_with_a_jump_list_linking_every_dimension_card():
    sec = section2(report_html.render_body(REPORT, {}))
    jump = re.search(r'<nav class="dimjump"[^>]*>(.*?)</nav>', sec, re.S)
    assert jump and sec.index("</h2>") < jump.start() < sec.index('<section class="dim"')
    links = re.findall(r'<a href="#([^"]+)"><span class="dnum">([\d.]+)</span> ([^<]+)</a>', jump.group(1))
    assert links == [("dim-tax-bands", "2.1", "Tax bands"), ("dim-vat-on-energy", "2.2", "VAT on energy")]
    card_ids = re.findall(r'<section class="dim" id="([^"]+)">', sec)
    assert [l[0] for l in links] == card_ids


def test_jump_list_label_is_translated():
    report_html.UI = report_html.STRINGS["sl"]
    sec = section2(report_html.render_body(REPORT, {}))
    label = re.search(r'<nav class="dimjump" aria-label="([^"]+)">', sec).group(1)
    assert label == report_html.STRINGS["sl"]["dim_jump"] != report_html.STRINGS["en"]["dim_jump"]


def test_a_report_without_section_2_dimensions_has_no_jump_list_or_cards():
    body = report_html.render_body("## 1. Motion\n\nText.\n\n### A subheading\n\nMore.\n", {})
    assert "dimjump" not in body and '<section class="dim"' not in body


@pytest.mark.parametrize("written,shown", [
    (("Settled", "Open questions", "Depends on your values"), ("Settled", "Open questions", "Depends on your values")),
    (("Ugotovljeno", "Odprta vprašanja", "Odvisno od vaših vrednot"), ("Settled", "Open questions", "Depends on your values")),
    (("Settled", "Factual Cruxes", "Value Cruxes"), ("Settled", "Open questions", "Depends on your values")),
])
def test_block_labels_in_section_2_are_marked_as_block_labels_without_their_colon(written, shown):
    report = REPORT
    for old, new in zip(("Settled", "Open questions", "Depends on your values"), written):
        report = report.replace(f"**{old}**:\n", f"**{new}**:\n")
    sec = section2(report_html.render_body(report, {}))
    assert re.findall(r'<strong class="blabel">([^<]+)</strong>', sec) == [*shown, "Settled"]
    assert '</strong>:' not in sec.replace('<strong>Does it cost more?</strong>', '')


def test_label_words_outside_section_2_stay_as_written():
    body = report_html.render_body(REPORT, {})
    assert "<strong>Settled</strong>: a label word in section 1." in body
    assert "<strong>Settled</strong>: a label in section 3." in body


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
