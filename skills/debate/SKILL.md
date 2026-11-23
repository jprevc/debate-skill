---
name: debate
description: Debate a yes/no Motion between Pro and Con Advocate subagents, with audited, traceable Evidence and a verdict-free Report. Use when the user wants to decide how to vote on a bill or referendum, settle a disputed claim, weigh a decision, or prepare counter-arguments for either side.
---

# Debate

You are the **orchestrator**. You frame the Motion with the user, dispatch fresh subagents Stage by Stage, and keep the record in the project folder. You don't argue the Motion or write the Report. You are the only participant who talks to the user, so you are the one who could leak the user's leanings. Keep the subagents **blind** to them: what you pass on is the scope and the record, nothing more.

`<skill dir>` is this skill's base directory. The shared rules for Evidence, Claims, responses and Evidence Requests are in `<skill dir>/reference/evidence.md`. Read that file before Framing.

## Project folder

One debate per project folder, which keeps what the user supplied apart from what the agents made:

```
<project>/
  README.md   what the debate is and where to find everything, for a person or a fresh session
  CLAUDE.md   loads README.md and the working rules into any Claude session opened here
  sources/    the user's own files, exactly as they gave them; agents never write here
  agent/      the debate record, everything the agents made
  outputs/    report.md  report.html  confrontation.md  (report-<lang>.*  confrontation-<lang>.md for a Translated Report)
              history/<N>/   the outputs a Revision replaced
```

- `<project>` is the folder the user names, or the directory they invoked the skill from when it is empty or holds only their documents for this Motion. Otherwise create `<project>` there as `<motion-slug>/`, and tell the user. It is never `<skill dir>`. Folder names carry no date: the date is in `state.md`.
- **`<folder>`** in this skill and in every dispatch is the absolute path of `agent/`. The scripts also accept `<project>`.
- `agent/state.md` is the single source of truth for progress. Every Stage reads its inputs from files and writes its outputs to files, so a fresh session can resume from `state.md` alone.

```
agent/
  state.md  motion.md  ledger.md  figures.json
  evidence/E-*.md
  evidence/files/          text the agents quote from: user-*.txt (extracts of sources/), fetched documents, web/
  notes-<prefix>.md                     one per Advocate (prefix: pro, con, pro-a, …)
  1-opening-<prefix>.md  2-rebuttal-<prefix>.md  4-rejoinder-<prefix>.md
  3-audit-batch-<N>.md  3-audit.md
  confrontation-check.md                the Checker's findings on the Confrontation
  figures-<lang>.json  motion-<lang>.md   only for a Translated Report
  revision-<N>-verify.md                the live check of every Evidence at the start of Revision N
  history/<N>/                          the case files and Stage 6 files that Revision N replaced
```

## Start or resume

The user may give a Motion, a link or a question. They may add `quick`, which skips the Rejoinder, `no-confrontation`, which skips Stage 6, and a folder.

- If the given folder or the current directory contains `agent/state.md`, or is `agent/` itself, **resume**. An older debate folder has `state.md` at its top, with no `agent/`: resume it in place, and the scripts write its Report there too. Read `state.md` and find the first Stage that isn't `done` or `skipped`. Tell the user which Stage you are resuming.
  - `outputs-done`: every dispatch finished, so run only Between Stages for it.
  - `running`: rerun only the dispatches whose output is incomplete. An Advocate's case file is complete when it has its final `## Evidence Requests` section, and an Audit batch is complete when its batch file exists. Keep the complete outputs.
  - `pending`: run the Stage.
  - If the Evidence Requests table in `state.md` has no `Needed`, `Tried`, `Where` and `Effort` columns (a debate from before they existed), add them first, and fill every row from the request blocks in the case files and from the log, by the rules in Between Stages step 3. Do this before running a Stage or rebuilding the Report, even for a finished debate.
  - A `state.md` from before Stage 6 existed has no Confrontation row. Add the row as `pending` and the line `- Confrontation: on`, and log it, so resuming a finished debate gives it a Confrontation.
  - If every Stage is `done` or `skipped`, the debate is finished. Tell the user when it finished, then ask whether to **revise** it (see Revision), or to start over in a new folder. Starting over is for a Motion or Dimensions that were framed wrongly; anything else is a Revision.
- Otherwise run Framing.

## Stage 0: Framing

1. **Motion.** State the input as one binary proposition, and say what "yes" and "no" each mean, including the status quo. If the user gave an open question, propose a Motion and get their agreement on the wording.
2. **Factual content.** If the Motion is purely a matter of taste or values, tell the user the protocol will add little, and offer to stop.
3. **Scope.** Ask the user only these, in one message:
   - the context or jurisdiction
   - the decision or vote date
   - links or documents they already have
   - arguments they have heard and want addressed

   Questions about which way they lean belong to no Stage. If the user volunteers their leanings, keep them out of every file and every dispatch.
4. **User files and Primary Text.** Put every file the user gives you in `sources/`, unchanged: if their files are loose in `<project>`, move them in and say so. Never edit, rename or copy a file inside `sources/`. Extract each one's text with `scripts/evidence.py import <folder> sources/<file> --name <short-slug>`, which writes `evidence/files/user-<slug>.txt` and records the original as the source's url. List each original with its extract under "Sources the user supplied" in `motion.md`. If the Motion concerns a specific document, cache it with `scripts/evidence.py fetch`, or import the user's copy. Then record its operative provisions as `E-PRIMARY-001` with `evidence.py quote`. Advocates search the cached text themselves. If you can't fetch it, ask the user for it.
5. **Dimensions.** Propose them: the document's provisions, or cross-cutting themes such as cost, legality or health effects. Let the user confirm or edit the list.
6. **Write the folder.**
   - `motion.md`, from `templates/motion.md`. Include Source Tier examples for this domain. Put each kind of document in exactly one tier, and cover every kind the debate is likely to quote: the government and its ministries, the proposers' own bill and memorandum, courts including dissenting opinions, and research papers (peer-reviewed in A, preprints and working papers in B, those funded by an interested party in C). The Report language is English unless the user asks for another. It is the language of every case file and the Report; quotes stay in their source's language.
   - `state.md`, from `templates/state.md`. In quick mode, mark Rejoinder and Rejoinder Audit `skipped`. With `no-confrontation`, set `- Confrontation: off` and mark Stage 6 `skipped`.
   - `agent/evidence/`, and the empty `outputs/`
   - `README.md` from `templates/project-readme.md` and `CLAUDE.md` from `templates/project-claude.md`, in `<project>`. Fill in every placeholder, with `<skill dir>` as its absolute path, and drop the parts that don't apply (groups, translation, quick mode). Status is "in progress", and the Report rows say "not written yet (Stage 5)". If either file already exists and isn't one of these, leave it and add the template's text under its own heading at the end.
7. **Groups.** With more than about six Dimensions, split them into groups (A, B, …) of related Dimensions. Each group gets its own Advocate per Side. Record the groups in `state.md`.
8. **Paper search.** Run `python3 <skill dir>/scripts/evidence.py papers --check`. If it prints a `WARNING` (no key, or little of today's budget left), pass it on to the user before the debate starts. The debate can go on without the key, but paper searches may run out partway through.
9. Mark Framing `done`, then tell the user the debate is starting and roughly how many subagent runs it will take.

## Dispatching

- Every subagent is **fresh**: a new `general-purpose` Agent for every Stage, never a continued one.
- Pass `model: "sonnet"` for Advocates and Auditors. Their work is high-volume research and checking, and on a large Motion they run 8 or more at a time. Leave the Judge and the Editor on the default model, because they do the synthesis the Report and the Confrontation depend on. The Checker runs on `"sonnet"`. If the user asks for a different model, use theirs.
- Run the Advocates of one Stage in parallel, in a single message, one per Side per group. Run Audit batches in parallel too.
- Each dispatch prompt is short. It names the brief to follow and the parameters, and nothing about the user beyond `motion.md`:

```
Read <skill dir>/prompts/advocate.md and follow it.
Folder: <absolute path of agent/>
Skill dir: <skill dir>
Side: PRO   (group: A, if any)
Stage: rebuttal
Dimensions: <names>
Output file: 2-rebuttal-pro-a.md
Opponent files: 1-opening-con-a.md
```

Wait for every subagent of a Stage to finish before running Between Stages.

If the harness stops a subagent from writing its output file, ask it to return the full text in its reply, then save that text to the file yourself, unchanged.

## Stages 1–6

Mark each Stage `running` in `state.md` when you dispatch it, `outputs-done` when every dispatch has finished, and `done` when Between Stages is complete.

| Stage | Dispatch | Opponent files |
|---|---|---|
| **1 Opening Case** | `advocate.md`, `Stage: opening`, `Output file: 1-opening-<prefix>.md` | none |
| **2 Rebuttal** | `advocate.md`, `Stage: rebuttal`, `Output file: 2-rebuttal-<prefix>.md` | the opposing group's `1-opening-*` |
| **3 Evidence Audit** | `auditor.md`, one dispatch per batch of about 20 Evidence IDs | n/a |
| **4 Rejoinder** | `advocate.md`, `Stage: rejoinder`, `Output file: 4-rejoinder-<prefix>.md`; in a Revision, also `Revision:` and `Earlier file:` | the opposing group's `2-rebuttal-*` |
| **4a Rejoinder Audit** | `auditor.md`, for Evidence created since the Audit, including new `E-USER-*` | n/a |
| **5 Judgment** | `judge.md`, with Folder and Skill dir only | n/a |
| **6 Confrontation** | `editor.md` and `checker.md`, in the loop below | n/a |

**Audit batches:**
- The Evidence Audit covers every Evidence file, including `E-PRIMARY-*` and `E-USER-*`. The Rejoinder Audit covers every Evidence file that no `3-audit-batch-*.md` lists. Go by the batch files, never by what an `## Audit` section contains: Advocates sometimes write in it.
- Batch each group's Evidence together where you can.
- After the batches return, write `3-audit.md`. It holds a table of counts per Side (passed, partial, failed, by tier), then every batch's "Findings worth the Judge's attention", copied verbatim, then links to the batch files. A Rejoinder Audit appends its own section to `3-audit.md`.
- Before writing `3-audit.md`, run the ledger and settle every `TIERMIX`: pick one tier for the source from the domain list in `motion.md`, set it in each listed Evidence file's `Source Tier` line, keep each Auditor's reasoning in Notes, and log the decision in `state.md`. Settle every `BADAUDIT` too: send the listed Evidence back to its batch's Auditor to correct the fields. Then tally the `Result` lines.

**Quick mode:** skip Stages 4 and 4a, and the Judge works from Stages 1–3. The Confrontation still runs, with no rejoinder turns.

**Stage 6 Confrontation.** The Editor retells each Dimension as turns between the Sides, built only from the record (`templates/confrontation.md`), and a Checker compares each turn with the Claims it names:

1. Dispatch a fresh Editor with `Mode: write`. It runs `ledger.py` until no `CONFRONTATION` line is left, and rebuilds `report.html`.
2. Dispatch a fresh Checker with `Round: 1`. It appends its findings to `confrontation-check.md`.
3. If it found issues, dispatch a fresh Editor with `Mode: fix`, then a fresh Checker with `Round: 2`. Stop there: log any issue still open in `state.md`, and tell the user at Finish.

Run Stage 6 straight after Judgment's Between Stages, with no checkpoint before it: it adds nothing to the record. Its Between Stages is only steps 1 and 4.

## Between Stages

After every Stage, in this order:

1. **Ledger.** Run `python3 <skill dir>/scripts/ledger.py <folder>`.
   - For each `DANGLING` ID (cited, but there is no file), dispatch a fresh Advocate for that Side to create the Evidence from a source it opens, or to withdraw the Claim.
   - For each `UNCITED` file, delete it.
   - Fix `SECTION`, `BADCLAIM`, `BADRESPONSE` and `BADREQUEST` lines yourself when the fix is mechanical: a translated heading or label (`Dimenzija:` → `Dimension:`), a Dimension name spelled differently from `motion.md`, or a wrong separator. When the fix changes substance, such as a Factual Claim with no Evidence or a wrong prefix, dispatch a fresh Advocate for that Side to fix those lines only.
   - For each `UNANSWERED` line, dispatch a fresh Advocate for that Side to add the missing responses to its Rebuttal.
   - Rerun the script until it prints no problems.
2. **Dimensions.** Read the "Proposed Dimensions" in the Opening Cases. Add the ones that are genuine aspects of the Motion to `motion.md`, and log each one in `state.md`. Tell the user what you added.
3. **Evidence Requests.**
   - Collect them from the Stage outputs and add them to `state.md` as `open`, one row per request, filling every column as the template's comment says:
     - `Needed`, `Where`, `Effort` and `For` from the latest Stage in which the request appears. When an Advocate raises it again, replace them with the new text.
     - `Tried` accumulates: the Advocate's "Why I can't get it", then its `Tried` attempts from every Stage. Keep the earlier attempts, add the new ones, and add your own triage and fetch attempts below, each starting with `orchestrator:` and saying what failed.
   - **Triage** every open request before asking the user. Advocates of one Stage work in parallel, and each sees only its own fetches, so many requests can be met without the user:
     - *Already in the record.* Search `ledger.md`, `evidence/files/` and `../sources/` for the requested document. Another Advocate may have fetched it already.
     - *Tool failure.* If `Tried` shows a certificate, DNS, timeout or JavaScript failure, retry those URLs with `scripts/evidence.py fetch`, with `--render` for JavaScript. Check that the domain is the institution's real one, and use `reference/sites.md` for the site's direct document links.
     - *Duplicates.* Merge requests from different Advocates for the same document into one row, with the IDs joined by ` + ` (`R-PRO-B-1 + R-CON-B-2`), and combine their `For` and `Tried`.
     - For either, mark the request `fulfilled` with the cached file's path under `evidence/files/` in "Fulfilled by". If the file holds only part of what was requested, mark it `partial` instead, and add a sentence starting `Still missing:` after the path; the rest still goes to the user. The requesting Advocate records Evidence from it in its next Stage. Fetch only the requested document, and quote nothing from it yourself.
   - Ask the user for the rest in one message, critical ones first. For each one give: what it is, which Claims it is for, the `Where` URLs and identifiers, the `Effort`, and how to hand it over (save the file into `sources/`, give its path, or paste the text). Put the requests whose `Effort` can't be met before the decision date last, and say so.
   - Put what the user supplies in `sources/` (pasted text as a `.txt` file there), `import` it, save it as `E-USER-NNN`, and mark the request `fulfilled` with that ID, or `partial` with a `Still missing:` sentence when it covers only part.
   - If the user can't get something, mark it `unavailable`.
   - The debate goes on either way: pending Claims stay pending, and the Report shows them as unsupported.
4. **Tool warnings.** If an Advocate's reply quotes a `WARNING` from `papers` (no OpenAlex key, a low or used-up budget, a refused key), pass it on to the user in the checkpoint. A used-up budget resets at midnight UTC; the debate goes on, with papers found through WebSearch until then.
5. **State.** Mark the Stage `done`, and log anything you reran or skipped.
6. **Checkpoint.** Give the user a short progress note and name the next Stage with its number of dispatches. Then wait: dispatch the next Stage only when the user says to continue. After Judgment, skip the checkpoint and go straight on to Stage 6.

## Finish

When Stage 6 is done or skipped, update `README.md`: the status line ("finished", the date, how many Evidence Requests are still unmet: `open`, `partial` or `unavailable`), the Report rows, and the Dimension count and groups if they changed. Then give the user:
- the paths to `outputs/report.html` (the Report with charts and the Confrontation tab; it opens offline in a browser), `outputs/report.md` and `outputs/confrontation.md`
- any Confrontation issue the Checker still reported after round 2; with `no-confrontation`, one line saying the Confrontation was skipped and that resuming the debate adds it
- the Judge's three-line summary of the main cruxes
- every Evidence Request still unmet (`open`, `partial` or `unavailable`), each with its status; `outputs/report.html` lists them too, with what was tried

If the user later supplies Evidence for one of those, add it and rerun from Stage 4a. That means a short audit, then a new Judgment and a new Confrontation. Anything bigger is a Revision.

## Revision

A Revision brings a finished debate up to date in its own folder, instead of a new debate: the Advocates of the affected groups rewrite their Rejoinders with what has changed, the new Evidence is audited, and the Judge writes a new Report that says what changed. The Opening Cases, the Rebuttals, the earlier Evidence and its Audit stay. `N` is the Revision's number: 1 for the first, then one more than the `- Revision:` line in `state.md`.

1. **What changed.** Ask the user, in one message:
   - what is new: the skill (new tools or rules; read `git log` in `<skill dir>` since the `Created` date, or the last Revision's date, for what), sources they supply, events since the last run (a court decision, an official analysis, new figures, a changed date), or a Dimension they want argued better
   - which groups it touches. Propose the groups yourself from what changed, and let the user confirm.

   Put supplied files in `sources/` and `import` them as in Framing. List each under "Sources the user supplied" in `motion.md`. Add a Dimension the user asks for to `motion.md` as at Between Stages step 2, and give it to a group.
2. **Recheck the record.** Run `python3 <skill dir>/scripts/evidence.py verify <folder> --live > <folder>/revision-<N>-verify.md`. It can take a few minutes. Every Evidence whose live source shows `partial`, `missing` or `unreachable` goes into the Revision's Audit, and the Advocates read the list.
3. **Archive.** Move into `agent/history/<N>/`: the affected groups' `4-rejoinder-*.md`, `confrontation-check.md`, and `figures*.json`. Move everything in `outputs/` except `history/` into `outputs/history/<N>/`, then fix its links to the record, which is now three levels up: `sed -i 's#\.\./agent/#../../../agent/#g' outputs/history/<N>/*.md outputs/history/<N>/*.html`. The archived `report.html` still opens offline. Never move or delete Evidence: `ledger.py` counts the archived case files as citing.
4. **State.** In `state.md`, set `- Revision: <N> (<date>)` (add the line under `Created` if it is missing), set Stages 4, 4a, 5 and 6 to `pending` (6 stays `skipped` with `Confrontation: off`), and log the Revision: its number, the date, what changed, the affected groups, and what you archived. A quick debate gets its Rejoinder now: set `- Mode: full`.
5. **Run Stages 4 to 6** as usual, with these differences:
   - Stage 4 dispatches only the affected groups. Add two lines to each dispatch: `Revision: <N> — <what changed, in one or two neutral sentences, nothing about the user's leanings>` and `Earlier file: history/<N>/4-rejoinder-<prefix>.md` (leave it out when the debate had no Rejoinder). The other groups' Rejoinders stand.
   - Stage 4a audits every Evidence that no `3-audit-batch-*.md` lists, plus the Evidence from step 2. Batch numbers continue from the highest one.
   - Add `Revision: <N>` to the Judge's dispatch.
   - Checkpoints and Between Stages run as usual.
6. **Finish** as usual. In `README.md`, the status says "revised (Revision N, YYYY-MM-DD)", and a line under "Start here" points to `outputs/history/` for the earlier Reports. If the debate has a Translated Report, translate the new Report as in Translated Report.

## Translated Report

If the user asks for the Report in another language, dispatch one fresh `general-purpose` agent to translate `outputs/report.md` into `outputs/report-<lang>.md` (for example `report-sl.md`), `agent/figures.json` into `agent/figures-<lang>.json`, and `outputs/confrontation.md`, when it exists, into `outputs/confrontation-<lang>.md`. Also write `agent/motion-<lang>.md` yourself: the Motion line in bold, and the Source Tier lines (`- A: …`) translated. The translation must mirror the original:

- the same sections, subsections, bullets and Evidence links, in the same order, including each Dimension's untitled lead paragraph;
- the domain's own terms, taken from the Evidence quotes (the act's and institutions' names as the sources write them), not literal translations;
- the Side names of that language's interface (Slovenian: Za / Proti); Claim and Evidence IDs stay as they are, because they are file links;
- the `· Status:` markers and block labels (Settled, Open questions, Depends on your values) in the original language, or in the target language where `report_html.py` lists them;
- in the Confrontation, every turn with the same ID line and Evidence links, the Dimension headings as the translated Report names them, and the turn headers in the target language where `templates/confrontation.md` lists them (Slovenian: `**Za · Uvodni nastop**`), otherwise in English.

Then run `python3 <skill dir>/scripts/ledger.py <folder>`, and have the translator fix any `CONFRONTATION` line about `confrontation-<lang>.md`; then run `uv run --script <skill dir>/scripts/report_html.py <folder> --lang <lang>`, which writes `outputs/report-<lang>.html`. If the Confrontation is written after a Report was already translated, translate it the same way then. Add the translated files to `README.md` (the Report rows, the `agent/` table and the rebuild commands). From then on, make every later fix to the Report or the Confrontation in both versions, and rebuild both.
