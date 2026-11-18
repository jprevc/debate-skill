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

The main agent stops after each Stage and asks before starting the next. When an Advocate needs a document only you can get, it raises an Evidence Request.

**Output:** `outputs/report.md` and a self-contained `outputs/report.html` with charts, info pop-ups and every Evidence ID clickable to its quote, translation and Audit verdict. On request, a translated Report (`report-<lang>.md/.html`).

## Requirements

- Claude Code
- `python3` (3.10+) and [`uv`](https://docs.astral.sh/uv/) (runs the scripts with their pinned dependencies)
- `pdftotext` (poppler-utils) for PDF sources
- Chromium for JavaScript sites (`evidence.py fetch --render`): `uvx playwright@1.65.2 install chromium`

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
outputs/   report.md, report.html (and report-<lang>.* for a translation)
```

If the folder already holds other things, the skill creates `<motion-slug>/` in it instead.

## Repository layout

```
.claude-plugin/        plugin and marketplace manifests
skills/debate/         the skill itself (everything that gets installed)
  SKILL.md             orchestrator instructions
  prompts/             Advocate, Auditor and Judge briefs
  reference/           shared Evidence rules, site recipes
  templates/           case, Evidence, audit, motion, state, report, methodology,
                       project README.md and CLAUDE.md
  scripts/             evidence.py (fetch, quote, verify, pxweb), ledger.py (checks),
                       report_html.py (HTML report), render.py (headless Chromium)
GLOSSARY.md, docs/     domain glossary, ADRs and agent docs for developing the skill
```
