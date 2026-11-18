#!/usr/bin/env python3
"""Rebuild ledger.md for a debate folder and check Evidence integrity.

Usage: python3 ledger.py <debate-folder>

Writes <debate-folder>/ledger.md and prints problems to stdout, one per line:
  DANGLING    a case file cites an Evidence ID that has no file (possible fabrication)
  UNCITED     an Evidence file no Claim or response cites
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
Exit code 0 always; problems are for the orchestrator to act on.
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


def main():
    folder = Path(sys.argv[1])
    folder = folder / "agent" if (folder / "agent").is_dir() else folder  # a project folder, or its agent/
    ev_dir = folder / "evidence"
    evidence = {}
    for f in sorted(ev_dir.glob("E-*.md")) if ev_dir.exists() else []:
        text = f.read_text(encoding="utf-8")
        evidence[f.stem] = (frontmatter(text), text)

    cited_by = {}  # evidence id -> set of case files
    for f in sorted(folder.glob("*.md")):
        if not CASE_RE.match(f.name):
            continue
        for eid in ID_RE.findall(f.read_text(encoding="utf-8")):
            cited_by.setdefault(eid, set()).add(f.stem)

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
