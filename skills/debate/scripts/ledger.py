#!/usr/bin/env python3
"""Rebuild ledger.md for a debate folder and check Evidence integrity.

Usage: python3 ledger.py <debate-folder>

Writes <debate-folder>/ledger.md and prints problems to stdout, one per line:
  DANGLING    a case file cites an Evidence ID that has no file (possible fabrication)
  UNCITED     an Evidence file no Claim or response cites (case files archived in history/<N>/ by a
              revision count as citing; they are not checked otherwise)
  SECTION     a case file lacks a required template heading (headings stay in English)
  BADCLAIM    a Claim line breaks the format in reference/evidence.md, names an unknown
              Dimension, uses another prefix, or lacks the Evidence its type needs
  DUPLICATE   a Claim ID is defined twice in one case file
  BADRESPONSE a "**Re ...**" line breaks the response format
  UNANSWERED  a Rebuttal has no response to an opposing Opening Claim
  BADREQUEST  an Evidence Request line breaks the format
  BADAUDIT    an audited Evidence file lacks a valid Result, Quote found, Cherry-picked or
              Source Tier value
  TIERMIX     Evidence quoted from the same cached source got different Source Tiers
  CONFRONTATION
              outputs/confrontation.md (when it exists) cites a Claim or response its turn's Side
              didn't make at that Stage in that Dimension, leaves one out of both its lists, paraphrases
              more than 3, cites Evidence that is missing, failed the Audit or isn't cited by what it
              paraphrases, breaks the turn format or order, or misses a Dimension; or a
              confrontation-<lang>.md doesn't mirror it
Exit code 0 after a run; problems are for the orchestrator to act on. Exit code 2, with nothing
written, when the argument is missing or the folder has no evidence/.
"""
import re
import sys
from pathlib import Path

ID_RE = re.compile(r"\bE-(?:PRIMARY|USER|PRO|CON)(?:-[A-Z])?-\d{3}\b")
CASE_RE = re.compile(r"^[124]-(opening|rebuttal|rejoinder)-")


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    fields = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fields[k.strip()] = re.sub(r"\s+#\s.*$", "", v).strip()
    return fields


def audit_field(text, name):
    m = re.search(rf"^- {re.escape(name)}:[ \t]*(.*)$", text, re.M)
    if not m or not m.group(1).strip() or m.group(1).startswith("<"):
        return ""
    return m.group(1).strip()


EID = r"E-(?:PRIMARY|USER|PRO|CON)(?:-[A-Z])?-\d{3}"
CID = r"(?:PRO|CON)(?:-[A-Z])?-\d+"
CLAIM_RE = re.compile(
    rf"^\*\*(?P<id>{CID})\*\* · Dimension: (?P<dim>.+?) · Type: (?P<type>Factual|Predictive|Value|Inference)"
    rf"(?: · Evidence: (?P<ev>{EID}(?:, {EID})*))?(?: · Pending Evidence: (?P<pend>R-{CID}(?:, R-{CID})*))?\s*$")
RESP_RE = re.compile(rf"^\*\*Re (?P<id>{CID})\*\* · (?:Rebut|Mitigate|Concede)(?: · Evidence: {EID}(?:, {EID})*)?\s*$")
REQ_RE = re.compile(rf"^\*\*R-{CID}\*\* · Priority: (?:critical|nice-to-have) · For: {CID}(?:, {CID})*\s*$")
FILE_RE = re.compile(r"^(?P<n>[124])-(?P<stage>opening|rebuttal|rejoinder)-(?P<side>pro|con)(?:-(?P<g>[a-z]))?$")
SECTIONS = {
    "opening": ["## Summary", "## Arguments the user has heard", "## Proposed Dimensions", "## Evidence Requests"],
    "rebuttal": ["## Summary", "## Arguments the user has heard", "## Evidence Requests"],
    "rejoinder": ["## Summary", "## Arguments the user has heard", "## Evidence audit follow-up", "## Evidence Requests"],
}


AUDIT_VALUES = {"Result": ("passed", "partial", "failed"), "Quote found": ("yes", "partially", "no"),
                "Cherry-picked": ("no", "partly", "yes"), "Source Tier": tuple("ABCD")}


def audit_result(text):
    """The Auditor's Result, or "not audited"; "unparsed" when the Result line is missing or malformed."""
    if not audit_field(text, "Quote found"):
        return "not audited"
    m = re.match(r"(passed|partial|failed)\b", audit_field(text, "Result"), re.I)
    return m.group(1).lower() if m else "unparsed"


def check_audits(evidence):
    problems = []
    for eid, (fm, text) in evidence.items():
        if not audit_field(text, "Quote found") and not audit_field(text, "Result"):
            continue
        for field, allowed in AUDIT_VALUES.items():
            v = audit_field(text, field)
            if not re.match(rf"(?:{'|'.join(allowed)})\b", v, re.I if field != "Source Tier" else 0):
                problems.append(f"BADAUDIT {eid}: {field} should start with {' | '.join(allowed)}, is '{v[:40]}'")
    return problems


def dimensions(folder):
    m = folder / "motion.md"
    if not m.exists():
        return set()
    text = m.read_text(encoding="utf-8")
    sec = re.search(r"^## Dimensions\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return {d.strip() for d in re.findall(r"^\s*\d+\.\s+\*\*(.+?)\*\*", sec.group(1) if sec else "", re.M)}


def check_cases(folder):
    problems, defined, opening_claims, answered = [], {}, {}, {}
    dims = dimensions(folder)
    for f in sorted(folder.glob("*.md")):
        fm = FILE_RE.match(f.stem)
        if not fm:
            continue
        text = f.read_text(encoding="utf-8")
        lines = text.splitlines()
        headings = {ln.strip() for ln in lines if ln.startswith("## ")}
        for h in SECTIONS[fm["stage"]]:
            if h not in headings:
                problems.append(f"SECTION {f.name}: missing '{h}'")
        prefix = fm["side"].upper() + (f"-{fm['g'].upper()}" if fm["g"] else "")
        key = (fm["side"], fm["g"])
        for i, ln in enumerate(lines, 1):
            if re.match(rf"^\*\*{CID}\*\*", ln):
                m = CLAIM_RE.match(ln)
                if not m:
                    problems.append(f"BADCLAIM {f.name}:{i}: format — {ln[:120]}")
                    continue
                cid = m["id"]
                if not re.fullmatch(rf"{prefix}-\d+", cid):
                    problems.append(f"BADCLAIM {f.name}:{i}: {cid} does not use this file's prefix {prefix}")
                if dims and m["dim"] not in dims:
                    problems.append(f"BADCLAIM {f.name}:{i}: {cid} names unknown Dimension '{m['dim']}'")
                if m["type"] != "Value" and not (m["ev"] or m["pend"]):
                    problems.append(f"BADCLAIM {f.name}:{i}: {cid} is {m['type']} but cites no Evidence")
                # A later Stage may restate a Claim under its existing ID (the restatement
                # supersedes); only a second definition within one file is a duplicate.
                if cid in defined and defined[cid].split(":")[0] == f.name:
                    problems.append(f"DUPLICATE {cid}: {defined[cid]} and {f.name}:{i}")
                defined[cid] = f"{f.name}:{i}"
                if fm["stage"] == "opening":
                    opening_claims.setdefault(key, []).append(cid)
            elif ln.startswith("**Re "):
                m = RESP_RE.match(ln)
                if not m:
                    problems.append(f"BADRESPONSE {f.name}:{i}: {ln[:120]}")
                elif fm["stage"] == "rebuttal":
                    answered.setdefault(key, set()).add(m["id"])
            elif ln.startswith("**R-") and not REQ_RE.match(ln):
                problems.append(f"BADREQUEST {f.name}:{i}: {ln[:120]}")
    for (side, g), got in answered.items():
        opp = ("con" if side == "pro" else "pro", g)
        missing = [c for c in opening_claims.get(opp, []) if c not in got]
        if missing:
            name = f"2-rebuttal-{side}{'-' + g if g else ''}.md"
            problems.append(f"UNANSWERED {name}: {', '.join(missing)}")
    return problems


# ---------- the Confrontation (outputs/confrontation.md) ----------

SIDES = ("PRO", "CON")
STAGES = ("opening", "rebuttal", "rejoinder")
# Turn header words, canonical key -> the words accepted for it (English, Slovenian)
SIDE_WORDS = {"PRO": ("Pro", "Za"), "CON": ("Con", "Proti")}
STAGE_WORDS = {"opening": ("Opening", "Uvodni nastop"), "rebuttal": ("Rebuttal", "Odgovor"), "rejoinder": ("Rejoinder", "Replika")}
NOT_SHOWN_WORDS = ("Not shown", "Ni prikazano")


def any_word(words):
    """A regex alternative of every word in a {key: words} map."""
    return "|".join(re.escape(w) for ws in words.values() for w in ws)


TURN_RE = re.compile(rf"^\*\*(?P<side>{any_word(SIDE_WORDS)}) · (?P<stage>{any_word(STAGE_WORDS)})\*\*\s*$")
# a bold line that starts with a Side word but is not a valid turn header ("**Pro · Rebuttal:**")
NEAR_TURN_RE = re.compile(rf"^\*\*(?:{any_word(SIDE_WORDS)})\b.*\*\*\s*$")
ITEM = rf"(?:Re )?{CID}"
IDLINE_RE = re.compile(rf"^\((?P<shown>{ITEM}(?:, {ITEM})*)(?:; (?:{'|'.join(NOT_SHOWN_WORDS)}): (?P<hidden>{ITEM}(?:, {ITEM})*))?\)\s*$")
# A Claim header as the record holds it; a restatement may carry a note after the ID ("**CON-A-2 (restated)**")
CLAIM_ANY_RE = re.compile(rf"^\*\*(?P<id>{CID})(?: \([^)]*\))?\*\* · Dimension: (?P<dim>.+?) · Type: \w+(?P<rest>.*)$")
RESP_ANY_RE = re.compile(rf"^\*\*Re (?P<id>{CID})\*\* · (?:Rebut|Mitigate|Concede)(?P<rest>.*)$")


def _canon(word, words):
    return next(k for k, ws in words.items() if word in ws)


def parse_confrontation(text):
    """Sections of a Confrontation: [{dim, line, turns: [{side, stage, label, line, text, shown, hidden, idline}]}].
    side is PRO | CON and stage opening | rebuttal | rejoinder; shown and hidden list items such as
    "PRO-1" or "Re CON-3"; idline is False when the turn does not end with a valid ID line."""
    sections, turn = [], None
    for i, ln in enumerate(text.splitlines(), 1):
        if ln.startswith("## "):
            sections.append({"dim": ln[3:].strip(), "line": i, "turns": []})
            turn = None
        elif (m := TURN_RE.match(ln)) and sections:
            turn = {"side": _canon(m["side"], SIDE_WORDS), "stage": _canon(m["stage"], STAGE_WORDS), "label": f"{m['side']} · {m['stage']}", "line": i,
                    "lines": [], "shown": [], "hidden": [], "idline": False}
            sections[-1]["turns"].append(turn)
        elif turn is not None:
            turn["lines"].append(ln)
    for sec in sections:
        for t in sec["turns"]:
            lines = [ln for ln in t.pop("lines") if ln.strip() and not ln.lstrip().startswith("<!--")]
            m = IDLINE_RE.match(lines[-1].strip()) if lines else None
            if m:
                t["idline"] = True
                t["shown"] = m["shown"].split(", ")
                t["hidden"] = m["hidden"].split(", ") if m["hidden"] else []
                lines = lines[:-1]
            t["text"] = "\n".join(lines)
    return sections


def record_items(folder):
    """What each Side said at each Stage: {(side, stage): {item: (dimension, Evidence IDs)}}, where an item is a
    Claim ID ("PRO-3") or a response ("Re CON-3"). A response's Dimension is that of the Claim it answers."""
    items, claim_dim = {}, {}
    for f in sorted(folder.glob("*.md")):
        fm = FILE_RE.match(f.stem)
        if not fm:
            continue
        key = (fm["side"].upper(), fm["stage"])
        for ln in f.read_text(encoding="utf-8").splitlines():
            if m := CLAIM_ANY_RE.match(ln):
                claim_dim.setdefault(m["id"], m["dim"].strip())
                items.setdefault(key, {})[m["id"]] = (m["dim"].strip(), set(ID_RE.findall(m["rest"])))
            elif m := RESP_ANY_RE.match(ln):
                items.setdefault(key, {})[f"Re {m['id']}"] = (None, set(ID_RE.findall(m["rest"])))
    for got in items.values():
        for it, (dim, ev) in got.items():
            if dim is None:
                got[it] = (claim_dim.get(it[3:], "?"), ev)
    return items


def check_mirror(original, path):
    """A translated Confrontation has the original's sections and turns, with the same IDs and Evidence."""
    def shape(t):
        return t["side"], t["stage"], t["shown"], t["hidden"], sorted(set(ID_RE.findall(t["text"])))
    sections = parse_confrontation(path.read_text(encoding="utf-8"))
    if len(sections) != len(original):
        return [f"CONFRONTATION {path.name}: {len(sections)} sections, but confrontation.md has {len(original)}"]
    problems = []
    for sec, orig in zip(sections, original):
        if [shape(t) for t in sec["turns"]] == [shape(t) for t in orig["turns"]]:
            continue
        bad = next((t for t, o in zip(sec["turns"], orig["turns"]) if shape(t) != shape(o)), None)
        where = f"{bad['line']}: {sec['dim']}, {bad['label']}" if bad else f"{sec['line']}: {sec['dim']}"
        problems.append(f"CONFRONTATION {path.name}:{where}: does not mirror '{orig['dim']}' in confrontation.md "
                        "(turns, IDs and Evidence must be the same)")
    return problems


def check_confrontation(folder, outdir, evidence):
    """CONFRONTATION problems in outputs/confrontation.md; evidence is {id: (frontmatter, text)}."""
    p = outdir / "confrontation.md"
    if not p.exists():
        return []
    problems = []
    items = record_items(folder)
    dims = dimensions(folder)
    text = p.read_text(encoding="utf-8")
    sections = parse_confrontation(text)
    for i, ln in enumerate(text.splitlines(), 1):
        if NEAR_TURN_RE.match(ln) and not TURN_RE.match(ln):
            problems.append(f"CONFRONTATION {p.name}:{i}: '{ln.strip()}' is not a turn header; write **<Side> · <Stage>**, e.g. **Pro · Rebuttal**")
    order = [(stage, side) for stage in STAGES for side in SIDES]
    for sec in sections:
        dim = sec["dim"]
        if dims and dim not in dims:
            problems.append(f"CONFRONTATION {p.name}:{sec['line']}: '{dim}' is not a Dimension in motion.md")
        last = -1
        for t in sec["turns"]:
            name = f"{t['side'].title()} {t['stage'].title()}"
            where = f"CONFRONTATION {p.name}:{t['line']}: {dim}, {name}"
            pos = order.index((t["stage"], t["side"]))
            if pos <= last:
                problems.append(f"{where}: out of record order (Pro, then Con, at Opening, Rebuttal, Rejoinder), or a second {name} turn")
            last = max(last, pos)
            if not t["idline"]:
                problems.append(f"{where}: does not end with an ID line, e.g. (PRO-1, Re CON-2; Not shown: PRO-3)")
            if len(t["shown"]) > 3:
                problems.append(f"{where}: paraphrases {len(t['shown'])} items; at most 3, the rest go under Not shown")
        turns = {(t["side"], t["stage"]): t for t in sec["turns"]}
        for stage in STAGES:
            for side in SIDES:
                said = {it: v for it, v in items.get((side, stage), {}).items() if v[0] == dim}
                name = f"{side.title()} {stage.title()}"
                t = turns.get((side, stage))
                if t is None:
                    if said:
                        problems.append(f"CONFRONTATION {p.name}:{sec['line']}: {dim}: no {name} turn, but the record has {', '.join(said)}")
                    continue
                where = f"CONFRONTATION {p.name}:{t['line']}: {dim}, {name}"
                for it in t["shown"] + t["hidden"]:
                    if it not in said:
                        problems.append(f"{where}: {it} is not a {side.title()} {stage} item in this Dimension")
                missing = [it for it in said if it not in t["shown"] + t["hidden"]]
                if missing:
                    problems.append(f"{where}: {', '.join(missing)} neither paraphrased nor listed under Not shown")
                backing = {e for it in t["shown"] if it in said for e in said[it][1]}
                for eid in dict.fromkeys(ID_RE.findall(t["text"])):
                    if eid not in evidence:
                        problems.append(f"{where}: {eid} has no Evidence file")
                    elif audit_result(evidence[eid][1]) == "failed":
                        problems.append(f"{where}: {eid} failed the Audit")
                    elif eid not in backing:
                        problems.append(f"{where}: {eid} is cited by none of {', '.join(t['shown']) or 'the items it paraphrases'}")
    for tp in sorted(outdir.glob("confrontation-*.md")):
        if re.fullmatch(r"confrontation-[a-z]{2,3}", tp.stem):  # a translation; not the Checker's confrontation-check.md
            problems += check_mirror(sections, tp)
    covered = {sec["dim"] for sec in sections}
    for d in sorted({v[0] for got in items.values() for v in got.values()} - covered):
        if not dims or d in dims:
            problems.append(f"CONFRONTATION {p.name}: Dimension '{d}' has Claims in the record but no section")
    return problems


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return
    if len(sys.argv) != 2:
        print("Usage: python3 ledger.py <debate-folder>", file=sys.stderr)
        sys.exit(2)
    folder = Path(sys.argv[1])
    folder = folder / "agent" if (folder / "agent").is_dir() else folder  # a project folder, or its agent/
    ev_dir = folder / "evidence"
    if not ev_dir.is_dir():
        print(f"{folder} is not a debate folder: it has no evidence/", file=sys.stderr)
        sys.exit(2)
    evidence = {}
    for f in sorted(ev_dir.glob("E-*.md")) if ev_dir.exists() else []:
        text = f.read_text(encoding="utf-8")
        evidence[f.stem] = (frontmatter(text), text)

    cited_by = {}  # evidence id -> set of case files
    # a revision archives the case files it replaces in history/<N>/; the earlier Report still cites their Evidence
    for f in sorted(folder.glob("*.md")) + sorted(folder.glob("history/*/*.md")):
        if not CASE_RE.match(f.name):
            continue
        name = f.relative_to(folder).with_suffix("").as_posix()
        for eid in ID_RE.findall(f.read_text(encoding="utf-8")):
            cited_by.setdefault(eid, set()).add(name)

    rows = []
    for eid, (fm, text) in evidence.items():
        rows.append(
            "| [{id}](evidence/{id}.md) | {by} | {title} | {pub} | {tier} | {found} | {cited} |".format(
                id=eid,
                by=fm.get("added_by", ""),
                title=fm.get("title", "").replace("|", "/"),
                pub=fm.get("publisher", "").replace("|", "/"),
                tier=audit_field(text, "Source Tier") or "—",
                found=audit_result(text),
                cited=", ".join(sorted(cited_by.get(eid, []))) or "—",
            )
        )

    out = [
        "# Evidence Ledger",
        "",
        "Generated by scripts/ledger.py — do not edit by hand.",
        "",
        f"Total: {len(evidence)}",
        "",
        "| ID | Added by | Title | Publisher | Tier | Audit | Cited in |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "",
    ]
    (folder / "ledger.md").write_text("\n".join(out), encoding="utf-8")

    for eid in sorted(set(cited_by) - set(evidence)):
        print(f"DANGLING {eid} cited in {', '.join(sorted(cited_by[eid]))}")
    for eid in sorted(set(evidence) - set(cited_by)):
        if not eid.startswith("E-PRIMARY"):
            print(f"UNCITED {eid}")
    for p in check_cases(folder):
        print(p)
    for p in check_audits(evidence):
        print(p)
    outdir = folder.parent / "outputs" if folder.name == "agent" else folder  # an older flat folder holds its outputs
    for p in check_confrontation(folder, outdir, evidence):
        print(p)
    tiers = {}  # source_file -> {tier: [ids]}
    for eid, (fm, text) in evidence.items():
        tier, src = audit_field(text, "Source Tier")[:1], fm.get("source_file", "")
        if tier and src:
            tiers.setdefault(src, {}).setdefault(tier, []).append(eid)
    for src, by_tier in sorted(tiers.items()):
        if len(by_tier) > 1:
            detail = "; ".join(f"{t}: {', '.join(ids)}" for t, ids in sorted(by_tier.items()))
            print(f"TIERMIX {src} — {detail}")
    print(f"ledger.md written: {len(evidence)} Evidence")


if __name__ == "__main__":
    main()
