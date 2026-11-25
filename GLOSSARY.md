# Debate

A structured, evidence-based debate over any binary Motion (political, technical, scientific or personal), run by opposing Advocates and resolved into a Report that helps the user decide and argue.

## Debate

**Motion**:
The binary proposition under debate, e.g. "Bill X should pass." Whatever the user wants decided is reframed into a Motion before the debate starts.
_Avoid_: Topic, question, issue

**Side**:
One of the two positions on a Motion: Pro (for) or Con (against).
_Avoid_: Team, camp

**Primary Text**:
The authoritative document the Motion is about (bill, contract, RFC, policy), recorded as the first Evidence. Optional: many Motions have none.
_Avoid_: Source document

**Dimension**:
A distinct aspect of the Motion debated separately, such as one provision of a bill or a theme like "cost" or "legality". Every Claim belongs to one Dimension.
_Avoid_: Sub-issue, aspect, topic

**Stage**:
One step of the debate protocol: Framing, Opening Case, Rebuttal, Evidence Audit, Rejoinder, Judgment, Confrontation.
_Avoid_: Phase, round

**Revision**:
A rerun of a finished debate in its own folder, from the Rejoinder on: the affected groups rewrite their Rejoinders with what changed since (new tools, sources or events), the new Evidence is audited, and the Judge writes a new Report that says what changed. The replaced files are kept in `history/<N>/`.
_Avoid_: Version, rerun, new debate

## Participants

**Advocate**:
A subagent assigned to argue one Side as strongly as the Evidence allows.
_Avoid_: Debater, agent

**Auditor**:
A neutral subagent that re-checks every cited Evidence against its original source and grades its quality.
_Avoid_: Fact-checker, verifier

**Judge**:
A neutral subagent that writes the Report from the record alone, without declaring a winner.
_Avoid_: Moderator, arbiter

**Editor**:
A neutral subagent that turns the finished record into a turn-by-turn rendering of the two Sides, adding no arguments and no Evidence of its own.
_Avoid_: Writer, narrator

**Checker**:
A neutral subagent that compares each turn of the Confrontation with the Claims and responses it names, and flags anything the record does not say. It checks the Short Report against the Report and the Confrontation the same way.
_Avoid_: Auditor (which checks Evidence against its sources), reviewer

**Summariser**:
A neutral subagent that writes the Short Report from the Report and the Confrontation, choosing and shortening but adding nothing.
_Avoid_: Editor (which writes the Confrontation), writer

## Evidence

**Claim**:
A single assertion made by an Advocate, which must cite Evidence unless it is explicitly a value or inference.
_Avoid_: Argument, point

**Evidence**:
A single recorded, citable excerpt from a source, quoted verbatim in its original language.
_Avoid_: Source, proof, citation

**Calc**:
Evidence that computes a number from numbers quoted in other Evidence, written and rechecked by `evidence.py calc`. It adds arithmetic to the record, never a fact.
_Avoid_: Calculation note, own estimate

**Evidence Ledger**:
The complete record of all Evidence gathered in one debate.
_Avoid_: Bibliography, source list

**Evidence Request**:
An Advocate's request for Evidence it cannot obtain itself and the user must supply.
_Avoid_: Help request

**Partly Fulfilled**:
The status of an Evidence Request where some of the requested Evidence was obtained and the rest is still missing. It counts as unmet, alongside open and unavailable.
_Avoid_: Fulfilled (partial)

**Pending Evidence**:
The status of a Claim whose supporting Evidence awaits an Evidence Request.

**Source Tier**:
The Auditor's grade of an Evidence's source by independence: A primary/authoritative, B independent expert, C interested party, D opinion.
_Avoid_: Credibility score

**Concession**:
An Advocate's explicit admission that it cannot counter an opposing Claim.

**Mitigation**:
An Advocate's acceptance of an opposing Claim combined with an argument that it matters less than claimed.

## Outcome

**Report**:
The final verdict-free document that maps the cruxes and equips the user to argue either Side.
_Avoid_: Verdict, summary

**Short Report**:
An optional one-page version of the Report for a reader who wants both Sides clearly: the key facts, one card per Dimension, and the detail behind a "More on this" panel. It adds nothing to the Report and the Confrontation it shortens.
_Avoid_: Summary, digest, brief

**Open Question**:
A disagreement that Evidence can settle (or shows is unsettled). In the Report it appears under "Open questions", each with its status.
_Avoid_: Factual Crux

**Value Question**:
A disagreement that turns on what one prioritizes, not on facts. In the Report it appears under "Depends on your values".
_Avoid_: Value Crux

**Confrontation**:
A rendering of the finished record as Turns between the Sides, one Dimension at a time, and the Stage that writes it. It is an edited rendering of the written cases, not a real conversation, and it carries no verdict.
_Avoid_: Debate (the whole protocol), exchange, conversation, face-off

**Turn**:
One Side's part of the Confrontation at one Stage in one Dimension: a short paraphrase of up to three of its Claims or responses, which it names.
_Avoid_: Message, round, bubble

**Cheat Sheet**:
The per-Side part of the Report listing the arguments opponents are likely to raise and the best Evidence-backed counters.
