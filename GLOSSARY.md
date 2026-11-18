# Debate

A structured, evidence-based debate over any binary Motion (political, technical, scientific or personal), run by opposing Advocates and resolved into a Report that helps the user decide and argue.

## Debate

**Motion**:
The binary proposition under debate, e.g. "Bill X should pass." Open questions are reframed into a Motion before the debate starts.
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
A neutral subagent that compares each turn of the Confrontation with the Claims and responses it names, and flags anything the record does not say.
_Avoid_: Auditor (which checks Evidence against its sources), reviewer

## Evidence

**Claim**:
A single assertion made by an Advocate, which must cite Evidence unless it is explicitly a value or inference.
_Avoid_: Argument, point

**Evidence**:
A single recorded, citable excerpt from a source, quoted verbatim in its original language.
_Avoid_: Source, proof, citation

**Evidence Ledger**:
The complete record of all Evidence gathered in one debate.
_Avoid_: Bibliography, source list

**Evidence Request**:
An Advocate's request for Evidence it cannot obtain itself and the user must supply.
_Avoid_: Help request

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

**Factual Crux**:
A disagreement that Evidence can settle (or shows is unsettled).

**Value Crux**:
A disagreement that turns on what one prioritizes, not on facts.

**Confrontation**:
A rendering of the finished record as Turns between the Sides, one Dimension at a time, and the Stage that writes it. It is an edited rendering of the written cases, not a real conversation, and it carries no verdict.
_Avoid_: Debate (the whole protocol), exchange, conversation, face-off

**Turn**:
One Side's part of the Confrontation at one Stage in one Dimension: a short paraphrase of up to three of its Claims or responses, which it names.
_Avoid_: Message, round, bubble

**Cheat Sheet**:
The per-Side part of the Report listing the arguments opponents are likely to raise and the best Evidence-backed counters.
