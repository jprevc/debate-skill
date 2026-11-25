"""report_html.py --short: the Short Report is built from report-short.md, the Report and figures.json, and its
template rules are checked.

Run: uv run --with markdown==3.7 --with pytest==9.2.0 pytest tests
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "debate" / "scripts"


def evidence(eid, result="passed", quote=None):
    return (f"---\nid: {eid}\nadded_by: {eid.split('-')[1]}\ntitle: Source of {eid}\npublisher: Office\n"
            f"url: https://example.org/{eid}\n---\n\n## Quote\n\n> {quote or f'Quote of {eid}.'}\n\n## Audit\n\n"
            f"- Result: {result}\n- Quote found: yes\n- Supports: yes\n- Cherry-picked: no\n- Source Tier: A\n")


MOTION = """# Motion

**The act should enter into force.**

## Scope

- Report language: English

## Dimensions

1. **Tax bands**: …
2. **Cost**: …
"""

REPORT = """# Debate Report: Should the act enter into force?

## 1. Motion and scope

The Motion.

## 2. Bottom line by Dimension

### Tax bands

The act replaces the flat rate with three bands.

**Settled**:

- Nobody pays more ([E-PRO-001](../agent/evidence/E-PRO-001.md)).

**Open questions**:

- **How many filers are affected?** · Status: unsettled — no count exists.
- **Does anyone pay more?** · Status: settled — both Sides accept no one does.

**Depends on your values**:

- If you weigh simplicity over fairness, the Evidence favors Con, because …

### Cost

**Settled**:

- It costs EUR 80 million a year ([E-CON-001](../agent/evidence/E-CON-001.md)).

**Open questions**:

- **Is the cost lasting?** · Status: leaning Con — the Fiscal Council says so.

## 3. Strength of each case

Text.
"""

SHORT = """# Debate Report: Should the act enter into force?

A one-page account of the debate.

1 December 2026 · short report

## At a glance <!-- glance -->

- **What the vote is on**: One act — Three tax bands replace a flat rate.
- **What it costs**: ≈ EUR 80 m a year — The Fiscal Council's estimate ([E-CON-001](../agent/evidence/E-CON-001.md)).
- **What a No keeps**: The flat rate — Nothing changes.
- **Who gains**: Top earners — Most of the relief goes to them.

## What it costs <!-- figures -->

The estimates differ.

### cost

**Pro**: We count the one-off part separately.

**Con**: Even the lasting part is large ([E-CON-001](../agent/evidence/E-CON-001.md)).

**Dimension**: Cost

## Where each case is stronger <!-- strength -->

What the Judge found.

**Pro**:

- **Who pays more**: nobody does.

**Con**:

- **Cost**: it is lasting.

Fine print.

## Dimension by Dimension <!-- dimensions -->

Each card shows both Sides.

### Tax bands

**Scale**: FC 79 · MoF 53 · EUR million a year

**Changes**: Three bands replace a flat rate.

**Key fact**: Nobody pays more ([E-PRO-001](../agent/evidence/E-PRO-001.md)).

**Pro**: The tax rises smoothly with income.

**Con**: The relief goes to one filer in five.

**Key question**: How many filers are affected? · Status: unsettled — no count exists.

**Pro concedes**:

- The count is unknown.

**Con concedes**:

- none

**Exchange**:

- **Pro · Opening**: Under current law the tax jumps; we smooth it ([E-PRO-001](../agent/evidence/E-PRO-001.md)).
- **Con · Opening**: The filers affected chose to exceed the limits.

## Depends on your values <!-- values -->

What turns on priorities.

| If you weigh more …, Pro is closer | Area | If you weigh more …, Con is closer |
|---|---|---|
| smooth taxes | Tax bands | simple taxes |

## What we don't know <!-- unknowns -->

Missing data.

1. **How many filers**: would settle the first question.
"""

FIGURES = {"figures": [{"id": "cost", "dimension": "Cost", "type": "bar", "title": "Cost estimates", "unit": "EUR million",
                        "categories": ["Ministry", "Fiscal Council"],
                        "series": [{"name": "Estimate", "values": [53, 80], "evidence": ["E-CON-001", "E-CON-001"]}],
                        "pins": [{"side": "con", "at": "Fiscal Council"}], "emphasis": ["Fiscal Council"]}]}


class ShortReport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        agent, out = self.root / "agent", self.root / "outputs"
        (agent / "evidence").mkdir(parents=True)
        out.mkdir()
        (agent / "motion.md").write_text(MOTION, encoding="utf-8")
        (agent / "evidence" / "E-PRO-001.md").write_text(evidence("E-PRO-001"), encoding="utf-8")
        (agent / "evidence" / "E-CON-001.md").write_text(
            evidence("E-CON-001", quote="Ocena: 79,6 mio EUR na leto."), encoding="utf-8")
        (agent / "evidence" / "E-CON-002.md").write_text(evidence("E-CON-002", "failed"), encoding="utf-8")
        (agent / "figures.json").write_text(json.dumps(FIGURES), encoding="utf-8")
        (out / "report.md").write_text(REPORT, encoding="utf-8")
        self.short = out / "report-short.md"
        self.short.write_text(SHORT, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, *extra):
        r = subprocess.run([sys.executable, str(SCRIPTS / "report_html.py"), str(self.root), "--short", *extra],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def page(self, name="report-short.html"):
        return (self.root / "outputs" / name).read_text(encoding="utf-8")

    def test_a_template_page_builds_without_problems(self):
        out = self.build()
        self.assertEqual(out.strip().splitlines(), ["report-short.html written: 1 figures, 2 Evidence embedded"])
        page = self.page()
        self.assertIn("<h1>Should the act enter into force?</h1>", page)  # the Report's heading, without its prefix
        self.assertIn('<article class="m" id="d-tax-bands">', page)
        self.assertIn('id="d-cost"', page)  # the Dimension attached to the figures section gets an anchor
        self.assertIn("≈&nbsp;EUR&nbsp;80&nbsp;m a year", page)

    def test_the_detail_panel_repeats_the_report_word_for_word_and_links_to_it(self):
        self.build()
        card = re.search(r'<article class="m" id="d-tax-bands">(.*?)</article>', self.page(), re.S).group(1)
        self.assertIn("Nobody pays more", card)
        self.assertIn("If you weigh simplicity over fairness", card)
        self.assertIn('<a href="report.html#dim-tax-bands">', card)
        self.assertIn('class="bub za"><span class="who">Pro · Opening</span>', card)
        self.assertNotIn("report.html#conf-", card)  # no confrontation.md, so no link to its tab

    def test_open_questions_are_counted_by_status_and_decided_ones_are_named(self):
        self.build()
        page = self.page()
        self.assertIn("Status of the 3 open questions", page)
        self.assertIn('<a href="#d-tax-bands">Does anyone pay more?</a>', page)
        self.assertIn('<a href="#d-cost">Is the cost lasting?</a>', page)

    def test_pins_and_figure_data_reach_the_page(self):
        self.build()
        fig = json.loads(re.search(r'id="figdata">(.*?)</script>', self.page(), re.S).group(1))
        self.assertEqual(fig["cost"]["pins"], [{"side": "CON", "n": "2", "at": "Fiscal Council"}])
        self.assertIn('<div class="note proti"><span class="pin" aria-hidden="true">2</span>', self.page())

    def test_template_breaks_are_reported(self):
        bad = (SHORT.replace("### Tax bands", "### Tax brackets")
               .replace("**Con**: The relief goes to one filer in five.", "")
               .replace("**Pro**: The tax rises smoothly with income.",
                        "**Pro**: " + "The tax rises smoothly with income and nobody pays more than before. " * 3)
               .replace("Nobody pays more ([E-PRO-001]", "Nobody pays more ([E-CON-002]")
               .replace('"Fiscal Council"', "x"))
        self.short.write_text(bad, encoding="utf-8")
        figs = json.loads(json.dumps(FIGURES))
        figs["figures"][0]["pins"] = [{"side": "con", "at": "Nowhere"}]
        (self.root / "agent" / "figures.json").write_text(json.dumps(figs), encoding="utf-8")
        out = self.build()
        self.assertIn("SHORT card 'Tax brackets': not a '### ' heading in Section 2 of report.md", out)
        self.assertIn("SHORT: Dimension 'Tax bands' has no card", out)
        self.assertIn("SHORT card 'Tax brackets': no **Con**", out)
        self.assertIn("SHORT: E-CON-002 failed the Audit", out)
        self.assertIn("SHORT figure 'cost': pin at 'Nowhere' is not one of its categories", out)

    def test_unbalanced_sides_are_reported(self):
        self.short.write_text(SHORT.replace("**Pro**: The tax rises smoothly with income.",
                                            "**Pro**: " + "The tax rises smoothly with income for everyone. " * 4), encoding="utf-8")
        self.assertIn("BALANCE card 'Tax bands': Pro 32 words, Con 8 words", self.build())

    def test_a_translation_must_mirror_the_original(self):
        sl = (SHORT.replace("**Pro**:", "**Za**:").replace("**Con**:", "**Proti**:")
              .replace("- **Con · Opening**: The filers affected chose to exceed the limits.",
                       "- **Proti · Uvodni nastop**: Prizadeti so mejo presegli sami [E-CON-001](../agent/evidence/E-CON-001.md)."))
        (self.root / "outputs" / "report-short-sl.md").write_text(sl, encoding="utf-8")
        (self.root / "outputs" / "report-sl.md").write_text(REPORT, encoding="utf-8")
        out = self.build("--lang", "sl")
        self.assertIn("SHORT report-short-sl.md: card 1 cites E-CON-001 differently from report-short.md", out)
        self.assertIn('<html lang="sl">', self.page("report-short-sl.html"))


if __name__ == "__main__":
    unittest.main()
