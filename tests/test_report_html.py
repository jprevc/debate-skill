"""Tests for skills/debate/scripts/report_html.py.

Run: uv run --with pytest --with markdown==3.7 pytest tests
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "debate" / "scripts"))
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
