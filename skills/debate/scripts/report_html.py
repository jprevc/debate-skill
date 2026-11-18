#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["markdown==3.7"]
# ///
"""Build report.html from a finished debate folder.

Usage: uv run --script report_html.py <project-folder> [--lang <code>]

The project folder holds sources/ (the user's files), agent/ (the debate record) and
outputs/ (the Reports); agent/ itself is accepted too. A folder with no agent/ is read as
an older, flat debate folder and the Report is written into it.

Reads outputs/report.md, then agent/figures.json (optional), agent/motion.md, the case
files and agent/evidence/E-*.md, and writes one self-contained outputs/report.html: the Report text with every Evidence ID opening
its quote, translation and Audit verdict; charts of the record (Evidence quality and Audit
results per Side, crux status per Dimension), each with an info pop-up that explains it;
and the Judge's figures from figures.json.

The interface language follows "Report language" in motion.md (English and Slovenian
have interface strings; others fall back to English). --lang <code> builds a translated
Report instead: it reads report-<code>.md, figures-<code>.json and motion-<code>.md
(each falling back to the untranslated file) and writes report-<code>.html.

Prints problems one per line, like ledger.py:
  FIGURE   a figure in figures.json is malformed or cites Evidence that is missing,
           failed the Audit or was never audited
  CAPTION  a figure's caption or note states a number (a rate, or an amount of 100 or
           more) that is neither in the figure's data nor in its Evidence quotes
  STATUS   an Open Question in the Report lacks its "· Status: …" marker
  LANG     the Report language has no interface strings; English is used
Exit code 0 always.
"""
import html
import json
import math
import re
import os
import sys
import urllib.parse
from pathlib import Path

import markdown

sys.path.insert(0, str(Path(__file__).parent))
from ledger import CID, CLAIM_RE, EID, FILE_RE, audit_field, frontmatter  # noqa: E402

SIDES = ("PRO", "CON")
TIERS = ("A", "B", "C", "D")
AUDIT = ("passed", "partial", "failed", "not audited")
STATUS = ("settled", "leaning Pro", "leaning Con", "unsettled")
problems = []
EVDIR = "evidence"  # the Evidence folder as seen from the page; set in main()


# ---------- interface language ----------
# Canonical keys stay English (statuses, audit results, Claim types); T() gives the label.
# Report markers are parsed in either language: "· Status: leaning Pro" or "· Stanje: v prid strani Za".

STRINGS = {
    "en": {
        "lang": "en", "title_prefix": "Debate Report: ", "kicker": "Debate Report",
        "motion_label": "Motion debated (the proposition the two Sides argued, not a recommendation):",
        "notice": "This report maps the evidence and the cruxes. It does not recommend a decision: once the facts are laid out, the choice depends on your values.",
        "nav_record": "The record at a glance", "nav_figures": "Key figures", "nav_report": "Full report", "nav_method": "Methodology",
        "method_word": "Methodology",
        "record_lede": "How well each Side's Evidence held up. Bar length is the share of that Side's Evidence; the number at the end is the count. These charts describe the sources, not who is right.",
        "tier_title": "Evidence by Source Tier", "tier_sub": "A primary · B independent expert · C interested party · D opinion",
        "audit_title": "Audit result", "audit_sub": "Quote found verbatim, in context, and supports the Claim",
        "items": "pieces of Evidence", "of": "of", "table_view": "Table view",
        "claims_word": "Claims", "concessions": "Concessions", "pending": "still pending Evidence",
        "crux_title": "Where each Dimension stands",
        "crux_sub": "Settled facts, open questions by status, and what depends on your values: the questions only your priorities can answer",
        "crux_cols": ("Dimension", "Settled", "Open questions", "Depends on your values"), "none": "none",
        "no_figure": "no figure", "evidence_col": " (Evidence)",
        "figures_lede": "What the act changes, in numbers. Every value comes from audited Evidence; hover a mark for its source, click it to read the quote.",
        "evidence_label": "Evidence",
        "PRO": "Pro", "CON": "Con",
        "passed": "passed", "partial": "partial", "failed": "failed", "not audited": "not audited",
        "settled": "settled", "leaning Pro": "leaning Pro", "leaning Con": "leaning Con", "unsettled": "unsettled", "value question": "value question",
        "Factual": "factual", "Inference": "inference", "Predictive": "predictive", "Value": "value",
        "Side": "Side", "Category": "Category", "Series": "Series", "Evidence": "Evidence",
        "label_Settled": "Settled", "label_Open questions": "Open questions", "label_Value questions": "Depends on your values",
        "about": "About", "close": "Close",
        "dlg": {"quote": "Quote", "translation": "Translation", "close": "Close", "source": "source", "file": "Evidence file",
                "audit": "Audit", "tier": "Source Tier", "found": "Quote found", "supports": "Supports", "cherry": "Cherry-picked",
                "funder": "Funder", "notes": "Auditor notes"},
        "info_tier_title": "Source Tiers",
        "info_tier_intro": "Each piece of Evidence is graded by the source the quote comes from, not by what it says. Every quote from the same document gets the same tier.",
        "tier_names": {"A": "A · primary", "B": "B · independent expert", "C": "C · interested party", "D": "D · opinion"},
        "tier_defs": {"A": "Primary or authoritative sources.", "B": "Independent expert bodies and factual reporting by quality media.",
                      "C": "Sources with a stake in the outcome. For these, the record states who runs or funds them.",
                      "D": "Opinion: columns, commentary, blogs, social media."},
        "tier_examples": "In this debate:",
        "tier_none": "Evidence the Auditor has not (yet) checked.",
        "info_tier_outro": "A higher tier means a more reliable source, not that a Side is right. Click an E-… label to see the tier of that piece of Evidence.",
        "info_audit_intro": "An independent Auditor reopened every piece of Evidence in its source document and checked three things: whether the quote really is in the source, whether the surrounding text weakens or reverses it (cherry-picking), and whether it supports the Claims that cite it.",
        "audit_defs": {"passed": "The quote is in the source verbatim, is not taken out of context, and fully supports every Claim that cites it.",
                       "partial": "The quote is in the source only in different wording with the same meaning, or its context limits it, or it only partly supports at least one Claim (e.g. a narrow finding stretched into a broad conclusion).",
                       "failed": "The quote is not in the source, means something different, or the source cannot be reached; or it supports none of the Claims that cite it.",
                       "not audited": "The Evidence has not been audited yet."},
        "info_audit_outro": "The audit details (quote found, context, support for each Claim, notes) are in each piece of Evidence's window.",
        "info_claims_title": "Claim types",
        "info_claims_intro": "Every Advocate's Claim carries a type label that says how much weight it bears.",
        "claim_defs": [("Factual", "A Claim about what is; it must cite Evidence."),
                       ("Inference", "A conclusion drawn from Evidence; it cites the Evidence it builds on and shows the reasoning step."),
                       ("Predictive", "“This will cause …”; it cites Evidence for the mechanism or for comparable cases elsewhere."),
                       ("Value", "A view on what is right or matters more (e.g. fairness); it has no Evidence, because no source can answer it, only your priorities."),
                       ("Concessions", "How many times this Side, in its responses, conceded a Claim of the other Side because it had no counter. Conceded Claims count as settled."),
                       ("Pending Evidence", "The Claim rests on a document the Advocate could not obtain (an open Evidence Request); the Report treats it as unsupported.")],
    },
    "sl": {
        "lang": "sl", "title_prefix": "Poročilo o razpravi: ", "kicker": "Poročilo o razpravi",
        "motion_label": "Teza razprave (trditev, o kateri sta strani razpravljali, ne priporočilo):",
        "notice": "To poročilo prikazuje dokaze in ključna vprašanja. Ne priporoča odločitve: ko so dejstva predstavljena, je izbira odvisna od vaših vrednot.",
        "nav_record": "Pregled gradiva", "nav_figures": "Ključni podatki", "nav_report": "Celotno poročilo", "nav_method": "Metodologija",
        "method_word": "Metodologija",
        "record_lede": "Kako so se obnesli dokazi posamezne strani. Dolžina stolpca je delež dokazov te strani, število na koncu pa njihovo število. Grafi opisujejo vire, ne tega, kdo ima prav.",
        "tier_title": "Dokazi po ravni vira", "tier_sub": "A primarni vir · B neodvisna strokovna institucija · C zainteresirana stran · D mnenje",
        "audit_title": "Rezultat preverjanja", "audit_sub": "Navedek je bil najden dobesedno, v kontekstu, in podpira trditev",
        "items": "dokazov", "of": "od", "table_view": "Prikaz v tabeli",
        "claims_word": "trditev", "concessions": "priznanj", "pending": "trditev še čaka na dokaze",
        "crux_title": "Stanje po področjih",
        "crux_sub": "Razrešena dejstva, odprta vprašanja po stanju in kar je odvisno od vaših vrednot: vprašanja, na katera lahko odgovorijo le vaše prioritete",
        "crux_cols": ("Področje", "Razrešeno", "Odprta vprašanja", "Odvisno od vaših vrednot"), "none": "jih ni",
        "no_figure": "ni podatka", "evidence_col": " (dokazi)",
        "figures_lede": "Kaj zakon spreminja, v številkah. Vsaka vrednost izhaja iz preverjenih dokazov; za vir se z miško postavite na oznako, s klikom preberete navedek.",
        "evidence_label": "Dokazi",
        "PRO": "Za", "CON": "Proti",
        "passed": "ustreza", "partial": "delno ustreza", "failed": "ne ustreza", "not audited": "ni preverjeno",
        "settled": "razrešeno", "leaning Pro": "v prid strani Za", "leaning Con": "v prid strani Proti", "unsettled": "nerazrešeno", "value question": "vrednostno vprašanje",
        "Factual": "dejstvenih", "Inference": "sklepov", "Predictive": "napovedi", "Value": "vrednostnih",
        "Side": "Stran", "Category": "Kategorija", "Series": "Niz", "Evidence": "Dokazi",
        "label_Settled": "Ugotovljeno", "label_Open questions": "Odprta vprašanja", "label_Value questions": "Odvisno od vaših vrednot",
        "about": "Pojasnilo", "close": "Zapri",
        "dlg": {"quote": "Navedek", "translation": "Prevod", "close": "Zapri", "source": "vir", "file": "Datoteka dokaza",
                "audit": "Preverjanje", "tier": "Raven vira", "found": "Navedek najden", "supports": "Podpira", "cherry": "Selektivno izbran",
                "funder": "Financer / povezanost", "notes": "Opombe preverjevalca"},
        "info_tier_title": "Ravni virov",
        "info_tier_intro": "Vsak dokaz dobi raven glede na vir, iz katerega je navedek, ne glede na to, kaj trdi. Vsi navedki iz istega dokumenta imajo isto raven.",
        "tier_names": {"A": "A · primarni vir", "B": "B · neodvisna strokovna institucija", "C": "C · zainteresirana stran", "D": "D · mnenje"},
        "tier_defs": {"A": "Primarni ali avtoritativni viri.", "B": "Neodvisne strokovne institucije in dejstveno poročanje kakovostnih medijev.",
                      "C": "Viri, ki jim izid ni vseeno. Pri teh virih je zapisano, kdo jih vodi ali financira.",
                      "D": "Mnenje: kolumne, komentarji, blogi, družbena omrežja."},
        "tier_examples": "V tej razpravi:",
        "tier_none": "Dokaz, ki ga revizor (še) ni pregledal.",
        "info_tier_outro": "Višja raven pomeni bolj zanesljiv vir, ne pa, da ima stran prav. Raven posameznega dokaza je vidna v njegovem oknu ob kliku na oznako E-….",
        "info_audit_intro": "Neodvisni revizor je vsak dokaz ponovno odprl v izvornem dokumentu in preveril tri stvari: ali navedek v viru res obstaja, ali ga okoliško besedilo ne oslabi ali obrne (iztrgan iz konteksta) in ali podpira trditve, ki se nanj sklicujejo.",
        "audit_defs": {"passed": "Navedek je v viru dobesedno, ni iztrgan iz konteksta in v celoti podpira vse trditve, ki ga navajajo.",
                       "partial": "Navedek je v viru le v drugačni ubeseditvi z enakim pomenom, ali pa ga kontekst omeji, ali pa vsaj eno trditev podpira le delno (npr. ozka ugotovitev, raztegnjena v širok sklep).",
                       "failed": "Navedka v viru ni, ima drugačen pomen ali vir ni dosegljiv, ali pa ne podpira nobene trditve, ki ga navaja.",
                       "not audited": "Revizija dokaza še ni bila opravljena."},
        "info_audit_outro": "Podrobnosti revizije (najden navedek, kontekst, podpora trditvam, opombe) so v oknu posameznega dokaza.",
        "info_claims_title": "Vrste trditev",
        "info_claims_intro": "Vsaka trditev zagovornika je označena z vrsto, ki pove, koliko teže nosi.",
        "claim_defs": [("dejstvena", "Trditev o tem, kar je; mora navesti dokaz."),
                       ("sklep", "Izpeljava iz dokazov; navede dokaze, na katere se opira, in pokaže korak sklepanja."),
                       ("napoved", "»To bo povzročilo …«; navede dokaze za mehanizem ali za primerljive primere drugod."),
                       ("vrednostna", "Stališče o tem, kaj je prav ali pomembneje (npr. pravičnost); nima dokazov, saj nanje ne more odgovoriti noben vir, temveč le vaše prioritete."),
                       ("priznanja", "Kolikokrat je ta stran v odgovorih priznala trditev nasprotne strani, ker nanjo ni imela protiargumenta. Priznane trditve se štejejo kot razrešene."),
                       ("čaka na dokaze", "Trditev se opira na dokument, ki ga zagovornik ni mogel pridobiti (odprta zahteva za dokaz); v poročilu velja za nepodprto.")],
    },
}
LANG_NAMES = {"english": "en", "en": "en", "slovenian": "sl", "slovene": "sl", "slovenščina": "sl", "slovensko": "sl", "sl": "sl"}
UI = STRINGS["en"]


def T(k):
    return UI.get(k, k)


# Report markers accepted in any supported language, mapped to the canonical key
STATUS_WORDS = {w: k for lang in STRINGS.values() for k in STATUS for w in (k, lang[k])}
STATUS_RE = "|".join(sorted(map(re.escape, STATUS_WORDS), key=len, reverse=True))
STATUS_MARK = rf"· (?:Status|Stanje): ({STATUS_RE})\b(?: \([^)]*\))?"
BLOCKS = ("Settled", "Open questions", "Value questions")
# Labels older Reports used before Open Questions and Value Questions were renamed; still read.
LEGACY_LABELS = {"Factual Cruxes": "Open questions", "Dejstvena ključna vprašanja": "Open questions",
                 "Value Cruxes": "Value questions", "Vrednostna ključna vprašanja": "Value questions"}
LABEL_WORDS = {lang[f"label_{k}"]: k for lang in STRINGS.values() for k in BLOCKS} | LEGACY_LABELS
LABEL_RE = "|".join(sorted(map(re.escape, LABEL_WORDS), key=len, reverse=True))


# ---------- reading the record ----------

def section(text, name):
    m = re.search(rf"^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        return ""
    return "\n".join(ln[1:].strip() for ln in m.group(1).splitlines() if ln.startswith(">") and ln[1:].strip()).strip()


def audit_result(text):
    found = audit_field(text, "Quote found").lower()
    if not found:
        return "not audited"
    m = re.match(r"(passed|partial|failed)\b", audit_field(text, "Result"), re.I)
    if m:  # the Auditor's own verdict (debates audited before the Result line existed fall through)
        return m.group(1).lower()
    return infer_result(found, audit_field(text, "Supports"), audit_field(text, "Cherry-picked").lower())


def infer_result(found, sup, cherry):
    """Read the verdict out of the free-text fields, by the rule in prompts/auditor.md step 5."""
    # the verdict is the first word after each Claim ID ("CON-C-9 yes: …", "Re PRO-D-11 (Pro) partly");
    # words later in the reason ("(Austria: no maximum)") are not verdicts
    supports = [s.lower() for s in re.findall(rf"\b{CID}(?:\s*\([^)]{{1,20}}\))?\s*:?\s*(yes|partly|no)\b", sup, re.I)]
    # a second verdict inside one entry: "PRO-B-3 yes for Germany's figure; partly for 'a standard instrument'"
    supports += [s.lower() for s in re.findall(r"(?:^|;\s*)(partly|no) for\b", sup, re.I)]
    if not supports and re.match(r"(yes|partly|no)\b", sup, re.I):
        supports = [sup.split()[0].lower()]
    if found.startswith("no") or (supports and all(s == "no" for s in supports)):
        return "failed"
    if found.startswith("partial") or cherry.startswith(("yes", "partly", "partially")) or any(s != "yes" for s in supports):
        return "partial"
    return "passed"


def load_evidence(folder):
    ev = {}
    for f in sorted((folder / "evidence").glob("E-*.md")):
        text = f.read_text(encoding="utf-8")
        fm = frontmatter(text)
        by = fm.get("added_by", "").upper()
        tier = audit_field(text, "Source Tier").upper()[:1]
        ev[f.stem] = {
            "id": f.stem,
            "side": next((s for s in SIDES if by.startswith(s)), "OTHER"),
            "title": fm.get("title", ""),
            "publisher": fm.get("publisher", ""),
            "published": fm.get("published", ""),
            "url": fm.get("url", ""),
            "quote": section(text, "Quote"),
            "translation": section(text, "Translation"),
            "tier": tier if tier in TIERS else "",
            "audit": audit_result(text),
            "found": audit_field(text, "Quote found"),
            "supports": audit_field(text, "Supports"),
            "cherry": audit_field(text, "Cherry-picked"),
            "funder": audit_field(text, "Funder/affiliation"),
            "notes": audit_field(text, "Notes"),
        }
    return ev


def load_cases(folder):
    claims, concessions = {}, {s: 0 for s in SIDES}
    for f in sorted(folder.glob("*.md")):
        fm = FILE_RE.match(f.stem)
        if not fm:
            continue
        side = fm["side"].upper()
        for ln in f.read_text(encoding="utf-8").splitlines():
            m = CLAIM_RE.match(ln)
            if m:
                claims[m["id"]] = {"side": side, "type": m["type"], "pending": bool(m["pend"])}
            elif ln.startswith("**Re ") and "· Concede" in ln:
                concessions[side] += 1
    return claims, concessions


def read_motion(folder, lang=None):
    """The Motion line and the domain's Source Tier examples ("- A: …" lines)."""
    p = folder / f"motion-{lang}.md" if lang else None
    if not p or not p.exists():
        p = folder / "motion.md"
    if not p.exists():
        return "", {}, ""
    text = p.read_text(encoding="utf-8")
    m = re.search(r"^\*\*(.+?)\*\*\s*$", text, re.M)
    tiers = dict(re.findall(r"^- ([ABCD]): (.+)$", text, re.M))
    rl = re.search(r"Report language:\s*([^.\n(]+)", text)
    return (m.group(1) if m else ""), tiers, (rl.group(1).strip() if rl else "")


def crux_map(report):
    """Per Dimension: settled count, Open Question statuses, Value Question count."""
    sec = re.search(r"^## 2\..*?\n(.*?)(?=^## 3\.|\Z)", report, re.S | re.M)
    out = []
    for m in re.finditer(r"^### (.+?)\n(.*?)(?=^### |\Z)", sec.group(1) if sec else "", re.S | re.M):
        dim, body = m.group(1).strip(), m.group(2)
        parts = {LABEL_WORDS[k]: v for k, v in re.findall(rf"^\*\*({LABEL_RE})\*\*(?: \([^)]*\))?:?(.*?)(?=^\*\*(?:{LABEL_RE})\*\*|\Z)", body, re.S | re.M)}
        bullets = lambda t: [b for b in re.findall(r"^\s*[-*] (.+)$", t or "", re.M)]  # noqa: E731
        statuses = []
        for b in bullets(parts.get("Open questions")):
            s = re.search(STATUS_MARK, b)
            if s:
                statuses.append(STATUS_WORDS[s.group(1)])
            else:
                problems.append(f"STATUS {dim}: Open Question without '· Status: …' — {b[:80]}")
        out.append({"dim": dim, "settled": len(bullets(parts.get("Settled"))),
                    "factual": statuses, "value": len(bullets(parts.get("Value questions")))})
    return out


# ---------- SVG helpers ----------

def esc(s):
    return html.escape(str(s), quote=True)


def nice_ticks(lo, hi, n=5):
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(k * mag for k in (1, 2, 2.5, 5, 10) if k * mag >= raw)
    start = math.floor(lo / step) * step
    ticks, t = [], start
    while t <= hi + step * 1e-9:
        ticks.append(round(t, 10))
        t += step
    if ticks[-1] < hi:
        ticks.append(ticks[-1] + step)
    return ticks


def localize_num(s):
    return s.replace(",", "\u2009").replace(".", ",").replace("\u2009", ".") if UI["lang"] == "sl" else s


def fmt(v):
    return localize_num(_fmt(v))


def fmt_full(v):
    return localize_num(_fmt_full(v))


def _fmt(v):
    if v is None:
        return "—"
    if abs(v) >= 10000:
        return f"{v / 1000:,.0f}K" if abs(v) < 1e6 else f"{v / 1e6:,.1f}M"
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.1f}"


def _fmt_full(v):
    return "—" if v is None else (f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}".rstrip("0").rstrip("."))


def legend(items):
    return '<div class="legend">' + "".join(
        f'<span><i style="background:{c}"></i>{esc(T(n))}</span>' for n, c in items) + "</div>"


def stacked_rows(rows, keys, colors, total_label):
    """Horizontal 100% stacked bars. rows: [(label, {key: count})]."""
    W, lw, bh, gap = 380, 44, 22, 14
    H = len(rows) * (bh + gap)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" class="chart">']
    for i, (label, counts) in enumerate(rows):
        y = i * (bh + gap) + 4
        total = sum(counts.values()) or 1
        out.append(f'<text x="0" y="{y + bh / 2 + 4}" class="lab">{esc(label)}</text>')
        x = lw
        avail = W - lw - 40
        segs = [(k, counts.get(k, 0)) for k in keys if counts.get(k, 0)]
        for j, (k, c) in enumerate(segs):
            w = avail * c / total
            gapw = 2 if j < len(segs) - 1 else 0
            tip = f"{label} · {T(k)}: {c} {T('of')} {total} {total_label} ({100 * c / total:.0f}{' %' if UI['lang'] == 'sl' else '%'})"
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w - gapw, 1):.1f}" height="{bh}" rx="{3 if j in (0, len(segs) - 1) else 0}" '
                       f'fill="{colors[k]}" data-tip="{esc(tip)}" tabindex="0"/>')
            x += w
        out.append(f'<text x="{W - 34}" y="{y + bh / 2 + 4}" class="lab num">{sum(counts.values())}</text>')
    out.append("</svg>")
    return "".join(out)


def table(headers, rows):
    h = "".join(f"<th>{esc(T(x))}</th>" for x in headers)
    b = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<details class="tv"><summary>{T('table_view')}</summary><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></details>'


# ---------- record charts ----------

def info(key, title, inner):
    """An "i" button that opens a pop-up explaining a chart; keeps definitions out of the page flow."""
    return (f'<button type="button" class="ib" popovertarget="info-{key}" aria-label="{esc(T("about"))}: {esc(title)}">i</button>'
            f'<div popover id="info-{key}" class="infopop"><div class="ih"><b>{esc(title)}</b>'
            f'<button type="button" class="ix" popovertarget="info-{key}" popovertargetaction="hide" aria-label="{esc(T("close"))}">×</button></div>{inner}</div>')


def info_tier(domain_tiers):
    dl = "".join(f'<dt>{esc(T("tier_names")[t])}</dt><dd>{esc(T("tier_defs")[t])}'
                 + (f' {esc(T("tier_examples"))} {esc(domain_tiers[t])}' if t in domain_tiers else "") + "</dd>" for t in TIERS)
    dl += f'<dt>{esc(T("not audited"))}</dt><dd>{esc(T("tier_none"))}</dd>'
    return info("tier", T("info_tier_title"), f'<p>{esc(T("info_tier_intro"))}</p><dl>{dl}</dl><p>{esc(T("info_tier_outro"))}</p>')


def info_audit():
    dl = "".join(f'<dt>{esc(T(k))}</dt><dd>{esc(T("audit_defs")[k])}</dd>' for k in AUDIT)
    return info("audit", T("audit_title"), f'<p>{esc(T("info_audit_intro"))}</p><dl>{dl}</dl><p>{esc(T("info_audit_outro"))}</p>')


def info_claims():
    dl = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in T("claim_defs"))
    return info("claims", T("info_claims_title"), f'<p>{esc(T("info_claims_intro"))}</p><dl>{dl}</dl>')


def record_charts(ev, claims, concessions, cruxes, domain_tiers):
    tier_col = {"A": "var(--seq-a)", "B": "var(--seq-b)", "C": "var(--seq-c)", "D": "var(--seq-d)", "not audited": "var(--none)"}
    audit_col = {"passed": "var(--good)", "partial": "var(--warning)", "failed": "var(--critical)", "not audited": "var(--none)"}
    side_name = {s: T(s) for s in SIDES}
    tiers = {s: {} for s in SIDES}
    audits = {s: {} for s in SIDES}
    for e in ev.values():
        if e["side"] not in SIDES:
            continue
        t = e["tier"] or "not audited"
        tiers[e["side"]][t] = tiers[e["side"]].get(t, 0) + 1
        audits[e["side"]][e["audit"]] = audits[e["side"]].get(e["audit"], 0) + 1
    tkeys = list(TIERS) + ["not audited"]
    out = [f'<section class="glance" id="record"><h2>{esc(T("nav_record"))}</h2>',
           f'<p class="lede">{esc(T("record_lede"))}</p>',
           f'<div class="grid2"><figure><figcaption><b>{esc(T("tier_title"))}{info_tier(domain_tiers)}</b><span>{esc(T("tier_sub"))}</span></figcaption>',
           stacked_rows([(side_name[s], tiers[s]) for s in SIDES], tkeys, tier_col, T("items")),
           legend([(k, tier_col[k]) for k in tkeys]),
           table(["Side"] + tkeys, [[side_name[s]] + [tiers[s].get(k, 0) for k in tkeys] for s in SIDES]),
           f'</figure><figure><figcaption><b>{esc(T("audit_title"))}{info_audit()}</b><span>{esc(T("audit_sub"))}</span></figcaption>',
           stacked_rows([(side_name[s], audits[s]) for s in SIDES], AUDIT, audit_col, T("items")),
           legend([(k, audit_col[k]) for k in AUDIT]),
           table(["Side"] + list(AUDIT), [[side_name[s]] + [audits[s].get(k, 0) for k in AUDIT] for s in SIDES]),
           "</figure></div>"]
    # claims / concessions / pending tiles
    types = ("Factual", "Inference", "Predictive", "Value")
    rows = []
    for s in SIDES:
        cs = [c for c in claims.values() if c["side"] == s]
        rows.append((side_name[s], len(cs), {t: sum(c["type"] == t for c in cs) for t in types},
                     concessions[s], sum(c["pending"] for c in cs)))
    out.append('<div class="tiles">')
    for i, (name, n, by_type, conc, pend) in enumerate(rows):
        bt = " · ".join(f"{v} {T(k)}" for k, v in by_type.items())
        out.append(f'<div class="tile"><span class="tl">{name}{info_claims() if i == 0 else ""}</span><span class="tv2">{n}<small> {T("claims_word")}</small></span>'
                   f'<span class="ts">{bt}</span><span class="ts">{conc} {T("concessions")} · {pend} {T("pending")}</span></div>')
    out.append("</div>")
    # crux map
    if cruxes:
        st_col = {"settled": "var(--st-settled)", "leaning Pro": "var(--pro)", "leaning Con": "var(--con)", "unsettled": "var(--st-open)"}
        out.append(f'<figure class="wide"><figcaption><b>{esc(T("crux_title"))}</b><span>{esc(T("crux_sub"))}</span></figcaption>'
                   '<table class="cruxmap"><thead><tr>' + "".join(f"<th>{esc(c)}</th>" for c in T("crux_cols")) + '</tr></thead><tbody>')
        for c in cruxes:
            chips = "".join(f'<i class="chip" style="--c:{st_col[s]}" data-tip="{esc(T(s))}" tabindex="0"></i>' for s in c["factual"]) or f'<span class="muted">{T("none")}</span>'
            anchor = "dim-" + re.sub(r"[^a-z0-9]+", "-", c["dim"].lower()).strip("-")
            vchips = f'<i class="vchip" data-tip="{esc(T("value question"))}" tabindex="0"></i>' * c["value"] or f'<span class="muted">{T("none")}</span>'
            out.append(f'<tr><td><a href="#{anchor}">{esc(c["dim"])}</a></td><td class="num">{c["settled"]}</td><td>{chips}</td>'
                       f'<td>{vchips}</td></tr>')
        out.append("</tbody></table>" + legend([(k, st_col[k]) for k in STATUS] + [("value question", "var(--value)")]) + "</figure>")
    out.append("</section>")
    return "".join(out)


# ---------- Judge's figures ----------

SERIES = [f"var(--s{i})" for i in range(1, 9)]


def ev_ids(x):
    return x if isinstance(x, list) else ([x] if x else [])


def fig_ids(f):
    """Every Evidence ID a figure cites: its series, plus caption_evidence (sources of numbers in the caption)."""
    ids = {i for s in f.get("series", []) for e in (s.get("evidence", []) if f.get("type") == "bar" else [s.get("evidence")]) for i in ev_ids(e)}
    return ids | set(ev_ids(f.get("caption_evidence")))


def check_figure(f, ev):
    fid = f.get("id", "?")
    ok = True
    for k in ("id", "title", "type", "series"):
        if k not in f:
            problems.append(f"FIGURE {fid}: missing '{k}'")
            ok = False
    if not ok:
        return False
    if f["type"] not in ("bar", "line"):
        problems.append(f"FIGURE {fid}: type must be bar or line")
        return False
    for s in f["series"]:
        if f["type"] == "bar":
            if len(s.get("values", [])) != len(f.get("categories", [])):
                problems.append(f"FIGURE {fid}: series '{s.get('name')}' has {len(s.get('values', []))} values for {len(f.get('categories', []))} categories")
                ok = False
            evl = s.get("evidence", [])
            if len(evl) != len(s.get("values", [])):
                problems.append(f"FIGURE {fid}: series '{s.get('name')}' needs one evidence entry per value")
                ok = False
            ids = [i for e in evl for i in ev_ids(e)]
            for v, e in zip(s.get("values", []), evl):
                if v is not None and not ev_ids(e):
                    problems.append(f"FIGURE {fid}: a value in '{s.get('name')}' cites no Evidence")
        else:
            if not s.get("points"):
                problems.append(f"FIGURE {fid}: line series '{s.get('name')}' has no points")
                ok = False
            ids = ev_ids(s.get("evidence"))
            if not ids:
                problems.append(f"FIGURE {fid}: series '{s.get('name')}' cites no Evidence")
        for i in ids:
            if i not in ev:
                problems.append(f"FIGURE {fid}: {i} does not exist")
            elif ev[i]["audit"] in ("failed", "not audited"):
                problems.append(f"FIGURE {fid}: {i} {'failed the Audit' if ev[i]['audit'] == 'failed' else 'was never audited'}")
    for i in ev_ids(f.get("caption_evidence")):
        if i not in ev:
            problems.append(f"FIGURE {fid}: caption_evidence {i} does not exist")
            ok = False
    if ok:
        check_caption(f, ev)
    return ok


NUM = r"(?<![\w.,])(\d{1,3}(?:[.,\u202f ]\d{3}(?!\d))+|\d+)(?:[.,](\d+))?(?:\s?(%))?"


def num_values(text):
    """Numbers in a text, read both as 1,234.5 and as 1.234,5; each with whether it was a percentage."""
    out = set()
    for m in re.finditer(NUM, text or ""):
        whole, frac, pct = m.group(1), m.group(2), bool(m.group(3))
        digits = re.sub(r"[.,\u202f ]", "", whole)
        cands = {float(digits + ("." + frac if frac else ""))}
        if re.fullmatch(r"\d{1,3}[.,]\d{3}", whole) and not frac:  # "1,195" may also be a decimal
            cands.add(float(whole.replace(",", ".")))
        out |= {(round(c, 2), pct) for c in cands}
    return out


def check_caption(f, ev):
    """Flag rates and amounts in a caption that are not in the figure's data, its note (where computations
    are shown), or the quotes of its Evidence and caption_evidence."""
    data = set()
    for s in f["series"]:
        vals = s.get("values", []) if f["type"] == "bar" else [c for p in s.get("points", []) for c in p]
        data |= {round(float(v), 2) for v in vals if v is not None}
    ids = fig_ids(f)
    quoted = {v for i in ids if i in ev for v, _ in num_values(ev[i]["quote"] + " " + ev[i]["translation"])}
    known = data | quoted | {v for v, _ in num_values(f.get("note", ""))}
    known |= {round(v * k, 2) for v in known for k in (100, 1000, 1e6, 0.001)}
    seen = {}
    for v, pct in num_values(f.get("caption", "")):
        seen[v] = pct or seen.get(v, False)
    for v, pct in sorted(seen.items()):
        if (pct or v >= 100) and not (1900 <= v <= 2100 and v.is_integer()) and v not in known:
            problems.append(f"CAPTION {f['id']}: {fmt_full(v)}{'%' if pct else ''} is in the caption but not in the figure's data, its note "
                            "or its Evidence quotes; check it against the chart, and cite its source in caption_evidence or show the computation in note")



def bar_chart(f):
    cats, series = f["categories"], f["series"]
    vals = [v for s in series for v in s["values"] if v is not None]
    hi = max(vals + [0])
    lo = min(vals + [0])
    ticks = nice_ticks(lo, hi)
    lo, hi = ticks[0], ticks[-1]
    ns = len(series)
    bh, bgap, ggap = 18, 2, 18
    lw = min(220, 8 + 7 * max(len(c) for c in cats))
    W, top = 680, 6
    plot = W - lw - 70
    gh = ns * bh + (ns - 1) * bgap
    H = top + len(cats) * (gh + ggap) + 24
    X = lambda v: lw + plot * (v - lo) / (hi - lo)  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" class="chart" aria-label="{esc(f["title"])}">']
    for t in ticks:
        out.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{top}" y2="{H - 22}" class="grid"/>'
                   f'<text x="{X(t):.1f}" y="{H - 6}" class="tick" text-anchor="middle">{fmt(t)}</text>')
    for ci, cat in enumerate(cats):
        y0 = top + ci * (gh + ggap)
        out.append(f'<text x="{lw - 8}" y="{y0 + gh / 2 + 4}" class="lab" text-anchor="end">{esc(cat)}</text>')
        for si, s in enumerate(series):
            v = s["values"][ci]
            y = y0 + si * (bh + bgap)
            if v is None:
                out.append(f'<text x="{X(0) + 4:.1f}" y="{y + bh / 2 + 4}" class="tick">{T("no_figure")}</text>')
                continue
            x0, x1 = sorted((X(0), X(v)))
            w = max(x1 - x0, 1)
            r = min(4, w / 2)
            # rounded data-end, square at baseline
            if v >= 0:
                d = f"M{x0:.1f},{y}h{w - r:.1f}a{r},{r} 0 0 1 {r},{r}v{bh - 2 * r}a{r},{r} 0 0 1 -{r},{r}h-{w - r:.1f}z"
            else:
                d = f"M{x1:.1f},{y}h-{w - r:.1f}a{r},{r} 0 0 0 -{r},{r}v{bh - 2 * r}a{r},{r} 0 0 0 {r},{r}h{w - r:.1f}z"
            ids = ", ".join(ev_ids(s["evidence"][ci]))
            tip = f"{cat}{' · ' + s['name'] if ns > 1 else ''}: {fmt_full(v)} {f.get('unit', '')} — {ids}"
            out.append(f'<path d="{d}" fill="{SERIES[si % 8]}" data-tip="{esc(tip)}" data-ev="{esc(ids)}" tabindex="0"/>')
            tx = (x1 + 6) if v >= 0 else (x0 - 6)
            out.append(f'<text x="{tx:.1f}" y="{y + bh / 2 + 4}" class="val" text-anchor="{"start" if v >= 0 else "end"}">{fmt_full(v)}</text>')
    out.append(f'<line x1="{X(0):.1f}" x2="{X(0):.1f}" y1="{top}" y2="{H - 22}" class="axis"/></svg>')
    leg = legend([(s["name"], SERIES[i % 8]) for i, s in enumerate(series)]) if ns > 1 else ""
    tv = table(["Category"] + [s["name"] + T("evidence_col") for s in series],
               [[c] + [f"{fmt_full(s['values'][i])} ({', '.join(ev_ids(s['evidence'][i]))})" for s in series] for i, c in enumerate(cats)])
    return "".join(out) + leg + tv


def line_chart(f):
    series = f["series"]
    xs = [p[0] for s in series for p in s["points"]]
    ys = [p[1] for s in series for p in s["points"]]
    xt, yt = nice_ticks(min(xs), max(xs), 6), nice_ticks(min(ys + [0]), max(ys))
    W, H, l, t, b = 680, 320, 56, 10, 44
    r = 24 + 7 * max(len(s["name"]) for s in series) if len(series) <= 4 else 24
    X = lambda v: l + (W - l - r) * (v - xt[0]) / (xt[-1] - xt[0])  # noqa: E731
    Y = lambda v: t + (H - t - b) * (1 - (v - yt[0]) / (yt[-1] - yt[0]))  # noqa: E731
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" class="chart" aria-label="{esc(f["title"])}">']
    for v in yt:
        out.append(f'<line x1="{l}" x2="{W - r}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/>'
                   f'<text x="{l - 6}" y="{Y(v) + 4:.1f}" class="tick" text-anchor="end">{fmt(v)}</text>')
    for v in xt:
        out.append(f'<text x="{X(v):.1f}" y="{H - b + 16}" class="tick" text-anchor="middle">{fmt(v)}</text>')
    out.append(f'<line x1="{l}" x2="{W - r}" y1="{Y(yt[0]):.1f}" y2="{Y(yt[0]):.1f}" class="axis"/>')
    if f.get("x_label"):
        out.append(f'<text x="{(l + W - r) / 2}" y="{H - 6}" class="tick" text-anchor="middle">{esc(f["x_label"])}</text>')
    if f.get("y_label"):
        out.append(f'<text x="{l}" y="{t - 0}" class="tick" dy="-0" transform="translate(-44 {H / 2}) rotate(-90 {l} {t})" text-anchor="middle">{esc(f["y_label"])}</text>')
    ends = []
    for si, s in enumerate(series):
        pts = sorted(s["points"])
        d = []
        for i, (x, y) in enumerate(pts):
            if i and s.get("step"):
                d.append(f"L{X(x):.1f},{Y(pts[i - 1][1]):.1f}")
            d.append(f"{'L' if i else 'M'}{X(x):.1f},{Y(y):.1f}")
        col = SERIES[si % 8]
        out.append(f'<path d="{"".join(d)}" fill="none" stroke="{col}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        ids = ", ".join(ev_ids(s.get("evidence")))
        for x, y in pts:
            tip = f"{s['name']} · {f.get('x_label', 'x')} {fmt_full(x)}: {fmt_full(y)} {f.get('unit', '')} — {ids}"
            out.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="4" fill="{col}" class="dot"/>'
                       f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="11" fill="transparent" data-tip="{esc(tip)}" data-ev="{esc(ids)}" tabindex="0"/>')
        ends.append([Y(pts[-1][1]), X(pts[-1][0]), s["name"], col])
    if len(series) <= 4:  # direct end labels with leader lines, spread to avoid collisions
        ends.sort()
        for i in range(1, len(ends)):
            ends[i][0] = max(ends[i][0], ends[i - 1][0] + 15)
        for i, (yl, xe, name, col) in enumerate(ends):
            ye = Y([p for s in series if s["name"] == name for p in sorted(s["points"])][-1][1])
            out.append(f'<line x1="{xe + 6:.1f}" y1="{ye:.1f}" x2="{W - r + 8}" y2="{yl:.1f}" class="leader"/>'
                       f'<text x="{W - r + 12}" y="{yl + 4:.1f}" class="lab">{esc(name)}</text>')
    out.append("</svg>")
    leg = legend([(s["name"], SERIES[i % 8]) for i, s in enumerate(series)]) if len(series) > 1 else ""
    rows = [[s["name"], fmt_full(x), fmt_full(y), ", ".join(ev_ids(s.get("evidence")))] for s in series for x, y in sorted(s["points"])]
    return "".join(out) + leg + table(["Series", f.get("x_label", "x"), f.get("y_label", "y"), "Evidence"], rows)


def figure_html(f, ev):
    body = bar_chart(f) if f["type"] == "bar" else line_chart(f)
    body = re.sub(r"(<svg.*?</svg>)", r'<div class="cw">\1</div>', body, count=1, flags=re.S)
    ids = sorted(fig_ids(f))
    src = ", ".join(f'<a href="{EVDIR}/{i}.md" data-ev="{i}">{i}</a>' + (f' <span class="flag">{T(ev[i]["audit"])}</span>' if i in ev and ev[i]["audit"] != "passed" else "") for i in ids)
    unit = f' <span class="unit">{esc(f["unit"])}</span>' if f.get("unit") else ""
    note = f'<p class="note">{esc(f["note"])}</p>' if f.get("note") else ""
    return (f'<figure class="fig" id="fig-{esc(f["id"])}"><figcaption><b>{esc(f["title"])}</b>{unit}'
            f'<span>{esc(f.get("caption", ""))}</span></figcaption>{body}{note}<p class="src">{T("evidence_label")}: {src}</p></figure>')


# ---------- page ----------

CSS = """
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;--s7:#6250d6;--s8:#e34948;
--pro:#2a78d6;--con:#eb6834;--seq-a:#1c5cab;--seq-b:#3987e5;--seq-c:#6da7ec;--seq-d:#9ec5f4;--none:#d6d5ce;
--good:#0ca30c;--warning:#fab219;--critical:#d03b3b;--st-settled:#52514e;--st-open:#c3c2b7;--value:#6250d6;--link:#1c5cab}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#0ca30c;--s7:#9085e9;--s8:#e66767;
--pro:#3987e5;--con:#d95926;--seq-a:#86b6ef;--seq-b:#3987e5;--seq-c:#256abf;--seq-d:#184f95;--none:#383835;--st-settled:#c3c2b7;--st-open:#52514e;--value:#9085e9;--link:#86b6ef}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#0ca30c;--s7:#9085e9;--s8:#e66767;
--pro:#3987e5;--con:#d95926;--seq-a:#86b6ef;--seq-b:#3987e5;--seq-c:#256abf;--seq-d:#184f95;--none:#383835;--st-settled:#c3c2b7;--st-open:#52514e;--value:#9085e9;--link:#86b6ef}
*{box-sizing:border-box}html{background:var(--page)}
body{margin:0;background:var(--page);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:960px;margin:0 auto;padding:32px 16px 80px}
header.top{margin-bottom:32px}header.top .kicker{color:var(--muted);font-size:13px;letter-spacing:.04em;text-transform:uppercase}
header.top h1{font-size:28px;line-height:1.25;margin:6px 0 12px;text-wrap:balance}
header.top .motion{color:var(--ink2);font-size:14px;margin:0 0 12px}header.top .motion span{color:var(--muted);display:block;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
header.top .meta{color:var(--ink2);font-size:14px}
.notice{border-left:3px solid var(--axis);padding:8px 14px;color:var(--ink2);margin:16px 0}
nav.toc{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:14px;margin:12px 0 0}
a{color:var(--link)}h2{font-size:22px;margin:48px 0 8px}h3{font-size:18px;margin:36px 0 8px;scroll-margin-top:16px}
.lede{color:var(--ink2);margin-top:0}
figure{margin:20px 0;background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:16px 16px 10px}
figcaption{display:flex;flex-direction:column;gap:2px;margin-bottom:10px}figcaption span{color:var(--ink2);font-size:14px}
.unit{color:var(--muted);font-size:13px;font-weight:400}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}.grid2 figure{margin:0}
@media (max-width:760px){.grid2{grid-template-columns:1fr}}
svg.chart{width:100%;height:auto;display:block;overflow:visible}.cw{overflow-x:auto}.cw svg.chart{min-width:520px}
svg .grid{stroke:var(--grid);stroke-width:1}svg .axis{stroke:var(--axis);stroke-width:1}svg .leader{stroke:var(--axis);stroke-width:1}
svg text{fill:var(--ink2);font-size:13px}svg .tick{fill:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}
svg .val{fill:var(--ink);font-size:12px;font-variant-numeric:tabular-nums}svg .num{font-variant-numeric:tabular-nums}
svg .dot{stroke:var(--surface);stroke-width:2}
svg [data-tip]{cursor:pointer;outline:none}svg rect[data-tip]:hover,svg path[data-tip]:hover,svg [data-tip]:focus{opacity:.8}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:13px;color:var(--ink2);margin:8px 0 4px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
details.tv{font-size:13px;margin-top:6px}details.tv summary{color:var(--muted);cursor:pointer}
table{border-collapse:collapse;width:100%;font-size:14px;margin:10px 0}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--ink2);font-weight:600}td.num{font-variant-numeric:tabular-nums}
.ib{display:inline-grid;place-items:center;width:18px;height:18px;margin-left:8px;border-radius:50%;border:1px solid var(--axis);background:none;color:var(--ink2);font:italic 600 12px/1 Georgia,serif;cursor:pointer;vertical-align:2px;padding:0}.ib:hover,.ib:focus-visible{border-color:var(--ink2);color:var(--ink)}
.infopop{max-width:min(560px,calc(100vw - 32px));max-height:80vh;overflow:auto;padding:16px 20px;border:1px solid var(--ring);border-radius:10px;background:var(--surface);color:var(--ink);font-size:14px;font-weight:400;line-height:1.5;box-shadow:0 8px 32px rgba(0,0,0,.25)}
.infopop::backdrop{background:rgba(0,0,0,.3)}.infopop .ih{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}.infopop .ix{background:none;border:0;font-size:22px;color:var(--ink2);cursor:pointer;padding:0 4px}
.infopop dl{margin:8px 0}.infopop dt{font-weight:600;margin-top:8px}.infopop dd{margin:2px 0 0;color:var(--ink2)}.infopop p{margin:6px 0;color:var(--ink2)}
.tiles{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px 0}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px;display:flex;flex-direction:column;gap:2px}
.tl{font-size:13px;color:var(--ink2)}.tv2{font-size:28px;font-weight:600}.tv2 small{font-size:14px;font-weight:400;color:var(--ink2)}.ts{font-size:13px;color:var(--ink2)}
@media (max-width:560px){.tiles{grid-template-columns:1fr}}
.cruxmap td:first-child{width:38%}.chip,.vchip{display:inline-block;width:14px;height:14px;border-radius:50%;margin:2px 4px 0 0;vertical-align:middle}
.chip{background:var(--c);cursor:pointer}.vchip{border:2px solid var(--value)}
.muted{color:var(--muted);font-size:13px}
.note{font-size:13px;color:var(--ink2);margin:6px 0 0}.src{font-size:13px;color:var(--ink2);margin:6px 0 0}
.flag{font-size:11px;padding:1px 6px;border-radius:8px;border:1px solid var(--axis);color:var(--ink2)}
article table{display:block;overflow-x:auto}
article blockquote{margin:12px 0;padding:4px 14px;border-left:3px solid var(--axis);color:var(--ink2)}
a.ev{white-space:nowrap;font-size:.9em}
.status{font-size:12px;padding:1px 8px;border-radius:10px;border:1px solid var(--axis);white-space:nowrap}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--page);font-size:13px;padding:6px 9px;border-radius:6px;max-width:320px;display:none;z-index:9}
dialog{max-width:680px;width:calc(100% - 32px);border:1px solid var(--ring);border-radius:12px;background:var(--surface);color:var(--ink);padding:20px}
dialog::backdrop{background:rgba(0,0,0,.4)}dialog h4{margin:0 0 4px;font-size:17px}dialog .m{color:var(--ink2);font-size:13px;margin-bottom:12px}
dialog blockquote{margin:8px 0;padding:4px 12px;border-left:3px solid var(--axis)}dialog .lang{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
dialog dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 12px;font-size:14px;margin:12px 0 0}dialog dt{color:var(--ink2)}dialog dd{margin:0}
dialog button{float:right;background:none;border:1px solid var(--axis);color:var(--ink);border-radius:6px;padding:2px 10px;cursor:pointer}
"""

JS = """
const EV=JSON.parse(document.getElementById('evdata').textContent);
const L=JSON.parse(document.getElementById('uidata').textContent);
const tip=document.getElementById('tip');
function showTip(el,x,y){tip.textContent=el.dataset.tip;tip.style.display='block';const r=tip.getBoundingClientRect();
 tip.style.left=Math.min(x+12,innerWidth-r.width-8)+'px';tip.style.top=Math.max(y-r.height-10,8)+'px';}
document.addEventListener('mousemove',e=>{const el=e.target.closest('[data-tip]');if(el)showTip(el,e.clientX,e.clientY);else tip.style.display='none';});
document.addEventListener('focusin',e=>{const el=e.target.closest('[data-tip]');if(el){const r=el.getBoundingClientRect();showTip(el,r.right,r.top);}});
document.addEventListener('focusout',()=>tip.style.display='none');
const dlg=document.getElementById('evdlg');
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function openEv(id){const e=EV[id];if(!e)return false;
 const q=e.quote?`<div class="lang">${L.quote}</div><blockquote>${esc(e.quote).replace(/\\n/g,'<br>')}</blockquote>`:'';
 const t=e.translation?`<div class="lang">${L.translation}</div><blockquote>${esc(e.translation).replace(/\\n/g,'<br>')}</blockquote>`:'';
 const row=(k,v)=>v?`<dt>${k}</dt><dd>${esc(v)}</dd>`:'';
 dlg.innerHTML=`<button onclick="this.closest('dialog').close()">${L.close}</button><h4>${esc(id)}: ${esc(e.title)}</h4>
 <div class="m">${esc(e.publisher)}${e.published?' · '+esc(e.published):''}${e.url?` · <a href="${esc(e.url)}" target="_blank" rel="noopener">${L.source}</a>`:''} · <a href="${esc(L.evdir)}/${esc(id)}.md">${L.file}</a></div>${q}${t}
 <dl>${row(L.audit,L.results[e.audit]||e.audit)}${row(L.tier,e.tier)}${row(L.found,e.found)}${row(L.supports,e.supports)}${row(L.cherry,e.cherry)}${row(L.funder,e.funder)}${row(L.notes,e.notes)}</dl>`;
 dlg.showModal();return true;}
document.addEventListener('click',e=>{const a=e.target.closest('[data-ev]');if(!a)return;const id=a.dataset.ev.split(',')[0].trim();
 if(openEv(id))e.preventDefault();});
document.addEventListener('keydown',e=>{if(e.key==='Enter'){const a=e.target.closest('svg [data-ev]');if(a)openEv(a.dataset.ev.split(',')[0].trim());}});
dlg.addEventListener('click',e=>{if(e.target===dlg)dlg.close();});
"""


def link_ids(md):
    # bare IDs become links; already-linked IDs ([E-…](../agent/evidence/E-….md)) are left alone
    return re.sub(rf"(?<![\[/\w-])({EID})(?![\]\w-])", lambda m: f"[{m.group(1)}]({EVDIR}/{m.group(1)}.md)", md)


def render_body(report_md, figures_by_dim):
    md = re.sub(r"^# .*\n", "", report_md, count=1)  # title goes in the header
    # the preamble before section 1 (date and mode line, translation note, disclaimer) is left out:
    # the page header carries the disclaimer, and a date like "17. 11. 2026" would render as a list
    md = md[md.index("\n## ") + 1:] if "\n## " in md else md
    md = re.sub(r"^(?![ \t]*[-*] |[ \t]*\d+\. )(.+)\n(?=[ \t]*(?:[-*]|\d+\.) )", r"\1\n\n", md, flags=re.M)  # lists need a blank line before them
    md = link_ids(md)
    body = markdown.markdown(md, extensions=["tables", "sane_lists"])
    # Evidence links, however the Report wrote the path (evidence/… or ../agent/evidence/…), point at EVDIR
    body = re.sub(rf'<a href="(?:[\w.%-]+/)*evidence/({EID})\.md">', lambda m: f'<a class="ev" href="{EVDIR}/{m.group(1)}.md" data-ev="{m.group(1)}">', body)
    body = re.sub(STATUS_MARK, lambda m: f'<span class="status">{esc(T(STATUS_WORDS[m.group(1)]))}</span>', body)
    # only block labels ("**Settled**:"); a label word in running text (old Methodology bullets) is left as written
    body = re.sub(rf"<strong>({LABEL_RE})</strong>(?: \([^)]*\))?(?=:)", lambda m: f"<strong>{esc(T('label_' + LABEL_WORDS[m.group(1)]))}</strong>", body)

    def h3(m):
        name = html.unescape(m.group(1))
        anchor = "dim-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return f'<h3 id="{anchor}">{m.group(1)}</h3>' + "".join(figures_by_dim.pop(name, []))
    body = re.sub(r"<h3>(.+?)</h3>", h3, body)
    body = re.sub(rf"<h2>((?:\d+\. )?{re.escape(T('method_word'))}\b)", r'<h2 id="methodology">\1', body, count=1)
    return body


def layout(p):
    """(agent dir, outputs dir) for a project folder, its agent/ folder, or an older flat debate folder."""
    p = p.resolve()
    if (p / "agent").is_dir():
        return p / "agent", p / "outputs"
    if p.name == "agent":
        return p, p.parent / "outputs"
    return p, p


def main():
    global UI, EVDIR
    args = sys.argv[1:]
    lang = None
    if "--lang" in args:
        i = args.index("--lang")
        lang = args[i + 1].lower()
        del args[i:i + 2]
    folder, outdir = layout(Path(args[0]))
    EVDIR = urllib.parse.quote(os.path.relpath(folder / "evidence", outdir))
    sfx = f"-{lang}" if lang else ""
    pick = lambda name, ext, d=folder: d / f"{name}{sfx}{ext}" if (d / f"{name}{sfx}{ext}").exists() else d / f"{name}{ext}"  # noqa: E731
    report_p = pick("report", ".md", outdir)
    if lang and report_p.name == "report.md":
        print(f"report-{lang}.md missing in {outdir}")
        return
    if not report_p.exists():
        print(f"report.md missing in {outdir}")
        return
    report = report_p.read_text(encoding="utf-8")
    motion, domain_tiers, report_lang = read_motion(folder, lang)
    code = lang or LANG_NAMES.get(report_lang.lower(), "en" if not report_lang else None)
    if code not in STRINGS:
        problems.append(f"LANG {lang or report_lang}: no interface strings; using English")
        code = "en"
    UI = STRINGS[code]
    ev = load_evidence(folder)
    for e in ev.values():  # relative links are written from agent/; the page lives in outputs/
        if e["url"] and not re.match(r"[a-z][a-z0-9+.-]*:", e["url"], re.I):
            e["url"] = urllib.parse.quote(os.path.relpath(folder / e["url"], outdir))
    claims, concessions = load_cases(folder)
    cruxes = crux_map(report)

    figs = []
    fp = pick("figures", ".json")
    if fp.exists():
        try:
            figs = json.loads(fp.read_text(encoding="utf-8")).get("figures", [])
        except json.JSONDecodeError as e:
            problems.append(f"FIGURE figures.json: invalid JSON — {e}")
    by_dim, general = {}, []
    for f in figs:
        if not check_figure(f, ev):
            continue
        h = figure_html(f, ev)
        (by_dim.setdefault(f["dimension"], []) if f.get("dimension") else general).append(h)
    known = {c["dim"] for c in cruxes}
    for d in list(by_dim):
        if d not in known:
            problems.append(f"FIGURE: dimension '{d}' is not a '### ' heading in section 2 of report.md; shown under Key figures")
            general += by_dim.pop(d)

    body = render_body(report, by_dim)
    title = re.match(r"^# (.+)$", report, re.M)
    title = title.group(1) if title else "Debate Report"
    cited = set(re.findall(EID, body)) | {i for f in figs for i in fig_ids(f)}
    evdata = {i: {k: v for k, v in ev[i].items() if k not in ("id", "side")} for i in sorted(cited) if i in ev}
    key = (f'<section id="figures"><h2>{esc(T("nav_figures"))}</h2><p class="lede">{esc(T("figures_lede"))}</p>'
           + "".join(general) + "</section>") if general else ""
    # the heading is the Report's own (neutral) title; the Motion is shown below it, labelled
    heading = re.sub(r"^(?:Debate Report|Poročilo o razpravi): ", "", title)
    mline = f'<p class="motion"><span>{esc(T("motion_label"))}</span> {esc(motion)}</p>' if motion else ""
    method = '<a href="#methodology">' + esc(T("nav_method")) + "</a>" if 'id="methodology"' in body else ""
    ui = dict(T("dlg"), results={k: T(k) for k in AUDIT}, evdir=EVDIR)
    page = f"""<!doctype html><html lang="{UI['lang']}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(heading[:100])}</title><style>{CSS}</style></head><body><main>
<header class="top"><div class="kicker">{esc(T("kicker"))}</div><h1>{esc(heading)}</h1>{mline}
<div class="notice">{esc(T("notice"))}</div>
<nav class="toc"><a href="#record">{esc(T("nav_record"))}</a>{f'<a href="#figures">{esc(T("nav_figures"))}</a>' if general else ''}<a href="#report">{esc(T("nav_report"))}</a>{method}</nav></header>
{record_charts(ev, claims, concessions, cruxes, domain_tiers)}
{key}
<article id="report"><h2>{esc(T("nav_report"))}</h2>{body}</article>
</main><div id="tip" role="tooltip"></div><dialog id="evdlg"></dialog>
<script type="application/json" id="evdata">{json.dumps(evdata, ensure_ascii=False).replace("</", "<\\/")}</script>
<script type="application/json" id="uidata">{json.dumps(ui, ensure_ascii=False).replace("</", "<\\/")}</script>
<script>{JS}</script></body></html>"""
    outdir.mkdir(exist_ok=True)
    out = outdir / f"report{sfx}.html"
    out.write_text(page, encoding="utf-8")
    for p in problems:
        print(p)
    print(f"{out.name} written: {len(figs)} figures, {len(evdata)} Evidence embedded")


if __name__ == "__main__":
    main()
