---
id: E-PRO-001
added_by: PRO            # PRO | CON | PRO-A | … | USER | MAIN
stage: opening           # framing | opening | rebuttal | rejoinder | between-stages
url: https://…           # or ../sources/<file> for user-supplied files (written by evidence.py import)
accessed: YYYY-MM-DD
title: …
author: …                # person or body; "unknown" if none is given
publisher: …
published: YYYY-MM-DD    # or YYYY, or "unknown"
language: sl             # ISO 639-1 code of the source
source_file: evidence/files/web/<cached>.txt   # written by scripts/evidence.py quote
source_lines: 41-41      # paragraph range of the quote in source_file
archive_url: https://web.archive.org/web/…   # only with a Wayback Machine snapshot (fetch --archive, EVIDENCE_ARCHIVE)
---
<!-- A calc (evidence.py calc, reference/evidence.md) has kind: calc, formula, inputs and result instead of
     source_file and source_lines, the formula as its Quote, and an Inputs section instead of Context. -->

## Quote

> verbatim excerpt, in the source's original language

## Translation

> into the Report language. Omit this section when the source is already in that language.

## Context

Before:

> the paragraph before the quote, verbatim

After:

> the paragraph after the quote, verbatim

Advocate's note: optional; who funds the source, a caveat

## Audit

<!-- Filled in by the Auditor only. -->


- Result: <passed | partial | failed>
- Quote found: <yes | partially | no>
- Supports: <Claim ID: yes | partly | no — reason>, one entry per citing Claim
- Cherry-picked: <no | partly | yes — what the context changes>
- Source Tier: <A | B | C | D>
- Funder/affiliation: <for tier C; otherwise "n/a">
- Notes: …
