# debate

A Claude Code skill that debates a yes/no **Motion** (a bill, a referendum question, a disputed claim, a decision) and produces an evidence-based Report that maps the arguments without recommending a decision.

## How it works

The main agent frames the Motion with you, then runs fresh subagents Stage by Stage. Every step is a file in a debate folder, so a run can be resumed from `state.md` and every Claim traced to its source.

| Stage | Who | What |
|---|---|---|
| 0 Framing | main agent, with you | Motion, Dimensions, Source Tier examples, Primary Text |
| 1 Opening | Pro and Con Advocates (per group of Dimensions) | Claims with verbatim, cached Evidence |
| 2 Rebuttal | Advocates | one response to every opposing Claim |
| 3 Audit | Auditors | reopen every source: quote found, context, support, Source Tier |
| 4 Rejoinder | Advocates | answer the Rebuttal, fix Evidence the Audit flagged |
| 4a Rejoinder Audit | Auditors | audit the new Evidence |
| 5 Judgment | Judge | `report.md`, `figures.json`, `report.html` |
| 6 Confrontation | Editor, then a Checker | `confrontation.md`: each Dimension retold turn by turn, Pro and Con, from the record only; a Confrontation tab in `report.html` (skip with `no-confrontation`) |

The main agent stops after each Stage and asks before starting the next. When an Advocate needs a document only you can get, it raises an Evidence Request.

**Output:** `outputs/report.md` and a self-contained `outputs/report.html` with charts, info pop-ups and every Evidence ID clickable to its quote, translation and Audit verdict. The Confrontation (`outputs/confrontation.md`, and a tab in the HTML Report) retells each Dimension as turns between the Sides; it is an edited rendering of the written cases, not a real conversation. On request, a translated Report (`report-<lang>.md/.html`, `confrontation-<lang>.md`).

## Requirements

- Claude Code
- `python3` (3.12+) and [`uv`](https://docs.astral.sh/uv/) (runs the scripts with their pinned dependencies)
- `pdftotext` (poppler-utils) for PDF sources
- Chromium for JavaScript sites (`evidence.py fetch --render`): `uvx playwright@1.65.2 install chromium`
- An OpenAlex API key for research-paper searches (`evidence.py papers`), free at https://openalex.org/settings/api. Set it as `OPENALEX_API_KEY`, in Claude Code under `"env"` in `~/.claude/settings.json`. Without it, searches share a small daily budget per network, and the debate warns you.
- Optional: `EVIDENCE_ARCHIVE=1` (set the same way) has the Wayback Machine snapshot every web page quoted as Evidence, so readers can check a quote after the page changes or disappears, and the HTML Report links the snapshot. Off by default, because it sends every quoted URL to archive.org. A site that is down is checked against its latest snapshot either way.

## Install

As a plugin:

```
/plugin marketplace add jprevc/debate-skill
/plugin install debate@debate-skill
```

Or, for development, link the skill folder:

```
ln -s "$PWD/skills/debate" ~/.claude/skills/debate
```

## Use

From a folder for this debate (empty, or holding your source documents):

```
/debate Should voters approve <act> at the referendum on <date>?
```

The folder is laid out as:

```
README.md  what the debate is and where everything is; CLAUDE.md points a new Claude session to it
sources/   your own files, never changed by the agents
agent/     the debate record: state, cases, audits, Evidence and cached sources
outputs/   report.md, report.html, confrontation.md (and report-<lang>.*, confrontation-<lang>.md for a translation)
```

If the folder already holds other things, the skill creates `<motion-slug>/` in it instead.

Run `/debate` again in a finished debate's folder to revise it rather than start over: tell it what has changed (new tools in the skill, new documents, new events), and the affected Advocates rewrite their Rejoinders, the new Evidence is audited, and the Judge writes a new Report that says what changed. Earlier Reports are kept in `outputs/history/`.

## Repository layout

```
.claude-plugin/        plugin and marketplace manifests
skills/debate/         the skill itself (everything that gets installed)
  SKILL.md             orchestrator instructions
  prompts/             Advocate, Auditor, Judge, Editor, Checker and Summariser briefs
  reference/           shared Evidence rules, site recipes, statistics sources, research papers
  templates/           case, Evidence, audit, motion, state, report, short report, methodology,
                       project README.md and CLAUDE.md
  scripts/             evidence.py (fetch, quote, calc, verify, archive, papers, data, pxweb), ledger.py (checks),
                       report_html.py (HTML report), short_html.py (Short Report, via report_html.py --short),
                       numcheck.py (the NUMBER check of both),
                       render.py (headless Chromium)
  assets/              fonts.css: the Short Report's embedded fonts (SIL OFL 1.1, see FONTS-LICENSE.md)
tests/                 tests for the scripts (not installed); run them with
                       uv run --with markdown==3.7 --with pytest==9.2.0 pytest tests
GLOSSARY.md, docs/     domain glossary, ADRs and agent docs for developing the skill
```

## License

[MIT](LICENSE). The fonts embedded in `skills/debate/assets/fonts.css` keep their own license, the SIL Open Font
License 1.1 (see `skills/debate/assets/FONTS-LICENSE.md`).
