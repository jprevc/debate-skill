# Debate state

- Motion: <one line, as in motion.md>
- Mode: full            # full | quick
- Report language: <e.g. Slovenian>
- Created: YYYY-MM-DD

## Advocate groups

<!-- "single" for one Advocate per Side, or one line per group: -->
- single

## Stages

| Stage | Status | Outputs |
|---|---|---|
| 0 Framing | pending | motion.md, evidence/E-PRIMARY-001.md |
| 1 Opening Case | pending | 1-opening-pro.md, 1-opening-con.md |
| 2 Rebuttal | pending | 2-rebuttal-pro.md, 2-rebuttal-con.md |
| 3 Evidence Audit | pending | 3-audit.md |
| 4 Rejoinder | pending | 4-rejoinder-pro.md, 4-rejoinder-con.md |
| 4a Rejoinder Audit | pending | 3-audit.md (appended) |
| 5 Judgment | pending | report.md |

<!-- Status: pending | running | outputs-done (Between Stages still to run) | done | skipped (quick mode) -->

## Evidence Requests

| ID | Priority | For | Status | Needed | Tried | Where | Effort | Fulfilled by |
|---|---|---|---|---|---|---|---|---|

<!--
ID: one row per document. Requests merged into one row are joined with " + ": R-PRO-B-1 + R-CON-B-2.
Needed, Where, Effort, For: from the latest Stage in which the request appears.
Tried: "Why I can't get it", then every attempt with what failed, from every Stage. Your own attempts start with "orchestrator:", e.g. "orchestrator: retried with --render, 403".
Status: open | partial | fulfilled | unavailable. partial = partly fulfilled: some of it was obtained, the rest is still missing.
Fulfilled by: an E-USER-* ID, or a cached file under evidence/files/ (or an original in ../sources/). For partial, add a sentence starting "Still missing:".
The HTML Report lists every open, unavailable and partial request with these columns, as written here; keep a "|" out of the cells.
-->

## Log

<!-- One line per event: Dimension added, Stage rerun, user-supplied Evidence, … -->
