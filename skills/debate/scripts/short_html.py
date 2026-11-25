"""Build the Short Report: outputs/report-short.md → outputs/report-short.html.

Usage: uv run --script report_html.py <project-folder> --short [--lang <code>]

Reads outputs/report-short[-<lang>].md (from templates/report-short.md), and from the same debate the
Report (report[-<lang>].md: each Dimension's Settled facts, Open questions and values, shown word for word
under "More on this"), figures[-<lang>].json, the Evidence files, and confrontation[-<lang>].md (only to
know whether the full Report has a Confrontation tab to link to). Writes one self-contained page: fonts,
charts, the Evidence quotes and the script are all inside it, so it opens offline.

Prints problems one per line, like report_html.py:
  SHORT    the short report breaks the template: a missing or unknown section, a card whose heading is not
           a Dimension of the Report, a Dimension with no card, a missing Pro or Con, an unknown figure,
           a bad pin, an Evidence link that is missing, failed the Audit or was never audited
  BALANCE  one Side gets more than twice the words of the other in a card, or more Exchange turns
  FIGURE   a figure the short report shows is malformed (the checks of report_html.py)
Exit code 0 always.
"""
import html
import json
import os
import re
import urllib.parse
from pathlib import Path

import report_html as R

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SECTIONS = ("glance", "figures", "strength", "dimensions", "values", "unknowns")
REQUIRED = ("glance", "strength", "dimensions", "values", "unknowns")

# Field labels: the canonical English key, then the words accepted for it in other languages.
LABELS = {
    "Name": ["Name", "Naslov"], "Provisions": ["Provisions", "Členi"], "Group": ["Group", "Skupina"],
    "Scale": ["Scale", "Obseg"], "Changes": ["Changes", "Kaj se spremeni"], "Figure": ["Figure", "Slika"],
    "Key fact": ["Key fact", "Ključno dejstvo"], "Pro": ["Pro", "Za"], "Con": ["Con", "Proti"],
    "Key question": ["Key question", "Ključno vprašanje"], "Pro concedes": ["Pro concedes", "Za priznava"],
    "Con concedes": ["Con concedes", "Proti priznava"], "Exchange": ["Exchange", "Razprava"],
    "Dimension": ["Dimension", "Področje"],
}
LABEL_KEY = {w: k for k, ws in LABELS.items() for w in ws}
LABEL_ALT = "|".join(sorted(map(re.escape, LABEL_KEY), key=len, reverse=True))
# a field runs to the next label, or to a blank line followed by a paragraph that is not a list item
FIELD_RE = re.compile(rf"^\*\*({LABEL_ALT})\*\*:[ \t]*(.*?)(?=^\*\*(?:{LABEL_ALT})\*\*:|\n[ \t]*\n(?=[ \t]*[^\s*-])|\Z)",
                      re.S | re.M)
SIDE_WORDS = {"pro": "PRO", "za": "PRO", "con": "CON", "proti": "CON"}
TURN_RE = re.compile(r"^\s*[-*] \*\*(Pro|Con|Za|Proti) · ([^*]+?)\*\*:?\s*(.+)$", re.M)
PIN_NO = {"PRO": "1", "CON": "2"}

SUI = {
    "en": {
        "brand": "Short report", "skip": "Skip to content", "nav": "Sections",
        "notice": "This page maps the evidence and the cruxes of the debate. It does not recommend a decision: "
                  "once the facts are laid out, the choice depends on your values.",
        "hint": "Each card has “More on this”; an E-… label opens the quote from its source.",
        "full_text": "Full text:", "full": "the full report",
        "more": "More on this", "more_sub": "findings, open questions, values, the exchange",
        "open_all": "Open all details", "close_all": "Close all details",
        "concedes": "What each Side concedes", "exchange": "How the debate went", "shortened": "shortened",
        "full_chapter": "The full chapter in the report →", "full_conf": "The full exchange, turn by turn →",
        "status_title": "Status of the {n} open questions",
        "groups": {"unsettled": "unsettled", "settled": "settled (both Sides accept the answer)",
                   "leaning Pro": "leaning Pro", "leaning Con": "leaning Con"},
        "chip": {"settled": "settled", "unsettled": "unsettled", "leaning Pro": "leaning Pro", "leaning Con": "leaning Con"},
        "stronger": {"PRO": "Pro is stronger on …", "CON": "Con is stronger on …"},
        "closer": {"PRO": "Closer to Pro", "CON": "Closer to Con"},
        "sources": "Sources:", "none": "none",
        "scale_aria": "Size",
        "drawer": {"source": "Source", "close": "Close the source", "passed": "passed the Audit",
                   "partial": "passed the Audit in part", "failed": "failed the Audit", "not audited": "not audited",
                   "cherry": "partly cherry-picked", "translation": "Translation",
                   "open": "Open the original document ↗", "file": "The full Evidence file, with its Audit",
                   "note": "The quote is verbatim, in the language of its source. The Source Tier says how reliable "
                           "the source is, not which Side is right."},
        "footer": "Written from the debate record: every fact links to a quote from its source, checked by an "
                  "independent Auditor. How the debate was run:",
        "method": "Methodology",
    },
    "sl": {
        "brand": "Kratko poročilo", "skip": "Preskoči na vsebino", "nav": "Poglavja",
        "notice": "Ta stran prikazuje dokaze in ključna vprašanja razprave. Ne priporoča odločitve: ko so dejstva "
                  "predstavljena, je izbira odvisna od vaših vrednot.",
        "hint": "Pri vsakem področju lahko odprete »Več o tem«; oznaka E-… odpre navedek iz vira.",
        "full_text": "Celotno besedilo:", "full": "celotno poročilo",
        "more": "Več o tem", "more_sub": "ugotovitve, odprta vprašanja, vrednote, potek razprave",
        "open_all": "Odpri vse podrobnosti", "close_all": "Zapri vse podrobnosti",
        "concedes": "Kaj priznava vsaka stran", "exchange": "Kako je potekala razprava", "shortened": "skrajšano",
        "full_chapter": "Celotno poglavje v poročilu →", "full_conf": "Celotna razprava, nastop za nastopom →",
        "status_title": "Stanje {n} odprtih vprašanj",
        "groups": {"unsettled": "nerazrešenih", "settled": "razrešenih (obe strani sprejemata odgovor)",
                   "leaning Pro": "v prid strani Za", "leaning Con": "v prid strani Proti"},
        "chip": {"settled": "razrešeno", "unsettled": "nerazrešeno", "leaning Pro": "v prid Za", "leaning Con": "v prid Proti"},
        "stronger": {"PRO": "Za je močnejša pri …", "CON": "Proti je močnejša pri …"},
        "closer": {"PRO": "Bližje Za", "CON": "Bližje Proti"},
        "sources": "Viri:", "none": "nič",
        "scale_aria": "Obseg",
        "drawer": {"source": "Vir", "close": "Zapri vir", "passed": "prestal preverjanje",
                   "partial": "preverjanje delno prestal", "failed": "ni prestal preverjanja", "not audited": "ni preverjeno",
                   "cherry": "deloma selektivno izbran", "translation": "Prevod",
                   "open": "Odpri izvorni dokument ↗", "file": "Celotna datoteka dokaza (z rezultatom preverjanja)",
                   "note": "Navedek je dobeseden, v jeziku vira. Raven vira pove, kako zanesljiv je vir, ne pa, "
                           "katera stran ima prav."},
        "footer": "Napisano iz gradiva razprave: vsako dejstvo se povezuje na navedek iz vira, ki ga je preveril "
                  "neodvisni revizor. Kako je razprava potekala:",
        "method": "Metodologija",
    },
}
CHIP_CLASS = {"settled": "settled", "unsettled": "open", "leaning Pro": "za", "leaning Con": "proti"}

problems = []
S = SUI["en"]


def esc(s):
    return html.escape(str(s), quote=True)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def words(s):
    return len(re.sub(r"\[(E-[A-Z0-9-]+)\]\([^)]*\)", "", s).split())


# ---------- inline markdown ----------

def ev_link(i):
    return f'<a class="ev" href="{R.EVDIR}/{i}.md">{i}</a>'


def inline(t, chips=True):
    """The inline Markdown the Report and the template use: Evidence links, other links, bold, italics."""
    t = html.escape(t.strip(), quote=False)
    t = re.sub(rf"\[({R.EID})\]\([^)]*\)", lambda m: ev_link(m.group(1)), t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<i>\1</i>", t)
    if chips:
        t = re.sub(R.STATUS_MARK + r"\.?", lambda m: " " + chip(R.STATUS_WORDS[m.group(1)]), t)
    # an Evidence label carries its own frame: drop the parentheses the Markdown wraps it in
    pill = r'<a class="ev" href="[^"]+">[^<]+</a>'
    return re.sub(r"\(\s*(" + pill + r"(?:\s*[,;]\s*" + pill + r")*)\s*\)", r"\1", t)


def nobreak(h):
    """Keep "≈ 1" and a number with a short unit ("1 mrd", "18 %") on one line; the rest may wrap."""
    h = re.sub(r"(?<=[≈~<>\d]) (?=[\d\w%€$£]{1,4}(?:[ ,.;]|$))(?![^<]*>)", "&nbsp;", h)
    return re.sub(r"\b([A-Z]{3}|[€$£]) (?=\d)(?![^<]*>)", r"\1&nbsp;", h)  # "EUR 80", "€ 5"


def chip(status):
    return f'<span class="chip {CHIP_CLASS[status]}">{esc(S["chip"][status])}</span>'


def bullets(text):
    return [b.strip() for b in re.findall(r"^\s*[-*] (.+)$", text or "", re.M)]


def fields(body):
    out = {}
    for label, val in FIELD_RE.findall(body):
        out[LABEL_KEY[label]] = val.strip()
    return out


# ---------- reading ----------

def sections(md):
    """{key: (heading, body)} for each "## Heading <!-- key -->"."""
    out, order = {}, []
    for m in re.finditer(r"^## (.+?)\s*<!--\s*(\w+)\s*-->\s*$\n(.*?)(?=^## |\Z)", md, re.S | re.M):
        head, key, body = m.group(1).strip(), m.group(2).strip(), m.group(3)
        if key not in SECTIONS:
            problems.append(f"SHORT section '{head}': unknown key <!-- {key} -->; use one of {', '.join(SECTIONS)}")
            continue
        out[key] = (head, body)
        order.append(key)
    for k in REQUIRED:
        if k not in out:
            problems.append(f"SHORT: no '## … <!-- {k} -->' section")
    return out, order


def report_dims(report):
    """{Dimension: {"Settled": [...], "Open questions": [...], "Value questions": [...]}} from Section 2."""
    sec = re.search(r"^## 2\..*?\n(.*?)(?=^## 3\.|\Z)", report, re.S | re.M)
    out = {}
    for m in re.finditer(r"^### (.+?)\n(.*?)(?=^### |\Z)", sec.group(1) if sec else "", re.S | re.M):
        body = m.group(2)
        parts = {R.LABEL_WORDS[k]: v for k, v in re.findall(
            rf"^\*\*({R.LABEL_RE})\*\*(?: \([^)]*\))?:?(.*?)(?=^\*\*(?:{R.LABEL_RE})\*\*|\Z)", body, re.S | re.M)}
        out[m.group(1).strip()] = {k: bullets(parts.get(k)) for k in R.BLOCKS}
    return out


def check_mirror(original, translated, name):
    """A translated short report has the original's sections, and per card the same Evidence, in the same order."""
    def shape(md):
        secs, _ = sections(strip_comments(md))
        cards = re.findall(r"^### .+?\n(.*?)(?=^### |\Z)", secs.get("dimensions", ("", ""))[1], re.S | re.M)
        return list(secs), [sorted(set(re.findall(rf"\[({R.EID})\]", c))) for c in cards]
    saved = problems[:]
    (ks, a), (kt, b) = shape(original), shape(translated)
    del problems[:]
    problems.extend(saved)
    if ks != kt:
        problems.append(f"SHORT {name}: sections {kt}, but report-short.md has {ks}")
    if len(a) != len(b):
        problems.append(f"SHORT {name}: {len(b)} cards, but report-short.md has {len(a)}")
    for i, (x, y) in enumerate(zip(a, b), 1):
        if x != y:
            problems.append(f"SHORT {name}: card {i} cites {', '.join(sorted(set(y) ^ set(x)))} differently from report-short.md")


def strip_comments(t):
    return re.sub(r"<!--(?!\s*\w+\s*-->).*?-->", "", t, flags=re.S)  # keeps the section keys


def num(s):
    s = s.strip()
    if S["code"] == "sl":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    return float(s)


# ---------- figures ----------

def fig_spec(f):
    """What the page script needs to draw a figure, after checking its pins."""
    keep = ("id", "type", "title", "unit", "categories", "series", "x_label", "y_label", "emphasis")
    spec = {k: f[k] for k in keep if k in f}
    pins = []
    for p in f.get("pins", []):
        side = SIDE_WORDS.get(str(p.get("side", "")).lower())
        at = p.get("at")
        if not side:
            problems.append(f"SHORT figure '{f.get('id')}': pin side '{p.get('side')}' is not pro or con")
            continue
        if f.get("type") == "bar" and at not in f.get("categories", []):
            problems.append(f"SHORT figure '{f.get('id')}': pin at '{at}' is not one of its categories")
            continue
        if f.get("type") == "line" and not (isinstance(at, list) and len(at) == 2):
            problems.append(f"SHORT figure '{f.get('id')}': a line-chart pin is at [x, y]")
            continue
        pins.append({"side": side, "n": PIN_NO[side], "at": at})
    spec["pins"] = pins
    for e in f.get("emphasis", []):
        if e not in f.get("categories", []):
            problems.append(f"SHORT figure '{f.get('id')}': emphasis '{e}' is not one of its categories")
    return spec


def figure_block(f, spec):
    legend = ""
    if f.get("type") == "bar" and len(f.get("series", [])) > 1:
        legend = '<span class="legend">' + "".join(
            f'<span><i class="k s{min(i + 1, 3)}"></i>{esc(s.get("name", ""))}</span>' for i, s in enumerate(f["series"])) + "</span>"
    ids = R.fig_ids(f)
    src = (f'<p class="fig-src">{esc(S["sources"])} ' + " ".join(ev_link(i) for i in ids) + "</p>") if ids else ""
    cap = "".join(f'<p class="chart-cap">{inline(f[k])}</p>' for k in ("caption", "note") if f.get(k))
    unit = f' <span class="unit">{esc(f["unit"])}</span>' if f.get("unit") else ""
    return (f'<figure class="fig-chart"><figcaption><b>{esc(f.get("title", ""))}</b>{unit}{legend}</figcaption>'
            f'<div class="chart" data-fig="{esc(f["id"])}" role="img" aria-label="{esc(f.get("title", ""))}"></div>{cap}{src}</figure>')


# ---------- pieces of the page ----------

def note(side, text, pinned):
    pin = f'<span class="pin" aria-hidden="true">{PIN_NO[side]}</span>' if pinned else ""
    cls = "za" if side == "PRO" else "proti"
    return f'<div class="note {cls}">{pin}<b>{esc(R.STRINGS[S["code"]][side])}</b>{inline(text)}</div>'


def pinned_sides(spec):
    return {p["side"] for p in (spec or {}).get("pins", [])}


def deep_panel(dim, rdims, card, sfx, has_conf, heading="h4"):
    p = rdims.get(dim, {})
    h = '<div class="deep-part">'
    for key in R.BLOCKS:
        items = p.get(key, [])
        if items:
            h += f'<{heading}>{esc(R.T("label_" + key))}</{heading}><ul>' + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul>"
    conc = {s: bullets(card.get(f"{'Pro' if s == 'PRO' else 'Con'} concedes", "")) for s in ("PRO", "CON")}
    if any(conc.values()):
        h += f'<{heading}>{esc(S["concedes"])}</{heading}><div class="args">'
        for s in ("PRO", "CON"):
            items = conc[s] or [S["none"]]
            h += (f'<div class="arg {"za" if s == "PRO" else "proti"}"><b>{esc(R.STRINGS[S["code"]][s])}</b><ul>'
                  + "".join(f"<li>{inline(i)}</li>" for i in items) + "</ul></div>")
        h += "</div>"
    turns = TURN_RE.findall(card.get("Exchange", ""))
    if turns:
        h += f'<{heading}>{esc(S["exchange"])} <span class="h5note">{esc(S["shortened"])}</span></{heading}><div class="chat">'
        for side, stage, text in turns:
            cls = "za" if SIDE_WORDS[side.lower()] == "PRO" else "proti"
            h += f'<div class="bub {cls}"><span class="who">{esc(side)} · {esc(stage.strip())}</span>{inline(text)}</div>'
        h += "</div>"
    links = f'<a href="report{sfx}.html#dim-{slug(dim)}">{esc(S["full_chapter"])}</a>'
    if has_conf:
        links += f'<a href="report{sfx}.html#conf-{slug(dim)}">{esc(S["full_conf"])}</a>'
    return h + f'<p class="deeplinks">{links}</p></div>'


def details(inner, sub=None):
    sub = S["more_sub"] if sub is None else sub
    return (f'<details class="deep"><summary>{esc(S["more"])} <span class="sum-sub">{esc(sub)}</span></summary>'
            f'<div class="deep-body">{inner}</div></details>')


def check_card_balance(where, pro, con):
    a, b = words(pro), words(con)
    if min(a, b) >= 8 and max(a, b) > 2 * min(a, b):
        problems.append(f"BALANCE {where}: Pro {a} words, Con {b} words")


def scale_html(text, top):
    parts = [x.strip() for x in text.split("·")]
    rows, unit = [], ""
    for x in parts:
        m = re.match(r"^(.+?)\s+(-?[\d.,]+)$", x)
        if m:
            try:
                rows.append((m.group(1), m.group(2), num(m.group(2))))
                continue
            except ValueError:
                pass
        unit = x
    if not rows:
        return f'<p class="mc-none">{inline(text)}</p>'
    bars = "".join(f'<div class="mc-row{" mf" if i else ""}"><span>{esc(lab)}</span>'
                   f'<i style="--w:{max(0, v) / top * 100:.1f}%"></i><b>{esc(raw)}</b></div>'
                   for i, (lab, raw, v) in enumerate(rows))
    aria = f'{S["scale_aria"]}: ' + ", ".join(f"{lab} {raw}" for lab, raw, _ in rows) + (f" {unit}" if unit else "")
    return f'<div class="mc" role="img" aria-label="{esc(aria)}">{bars}<div class="mc-u">{esc(unit)}</div></div>'


def scale_max(cards):
    top = 0
    for c in cards:
        for x in c.get("Scale", "").split("·"):
            m = re.match(r"^.+?\s+(-?[\d.,]+)$", x.strip())
            if m:
                try:
                    top = max(top, num(m.group(1)))
                except ValueError:
                    pass
    return top or 1


# ---------- the page ----------

def build(folder, outdir, lang, code):
    """Write outputs/report-short[-<lang>].html; return (path, figures shown, Evidence embedded) or None."""
    global S
    S = dict(SUI.get(code, SUI["en"]), code=code)
    sfx = f"-{lang}" if lang else ""
    p = outdir / f"report-short{sfx}.md"
    if not p.exists():
        print(f"{p.name} missing in {outdir}: write it from templates/report-short.md first")
        return None
    md = strip_comments(p.read_text(encoding="utf-8"))
    if lang and (outdir / "report-short.md").exists():
        check_mirror((outdir / "report-short.md").read_text(encoding="utf-8"), md, p.name)
    rp = outdir / f"report{sfx}.md"
    report = rp.read_text(encoding="utf-8") if rp.exists() else ""
    if not report:
        problems.append(f"SHORT: {rp.name} missing; the 'More on this' panels need it")
    rdims = report_dims(report)
    has_conf = (outdir / f"confrontation{sfx}.md").exists()

    ev = R.load_evidence(folder)
    for e in ev.values():
        if e["url"] and not re.match(r"[a-z][a-z0-9+.-]*:", e["url"], re.I):
            e["url"] = urllib.parse.quote(os.path.relpath(folder / e["url"], outdir))
    figs = {}
    fp = folder / f"figures{sfx}.json"
    if not fp.exists():
        fp = folder / "figures.json"
    if fp.exists():
        try:
            figs = {f.get("id"): f for f in json.loads(fp.read_text(encoding="utf-8")).get("figures", [])}
        except json.JSONDecodeError as e:
            problems.append(f"FIGURE {fp.name}: invalid JSON — {e}")
    shown = {}

    def use_fig(fid, where):
        f = figs.get(fid)
        if not f:
            problems.append(f"SHORT {where}: figure '{fid}' is not in {fp.name}")
            return None, None
        if fid not in shown:
            if not R.check_figure(f, ev):
                return None, None
            shown[fid] = fig_spec(f)
        return f, shown[fid]

    title_m = re.search(r"^# (.+)$", md, re.M)
    title = title_m.group(1).strip() if title_m else "Short report"
    title = re.sub(r"^(?:Debate Report|Poročilo o razpravi): ", "", title)  # as the full Report's heading
    pre = md[title_m.end():] if title_m else md
    pre = pre.split("\n## ", 1)[0]
    paras = [x.strip() for x in re.split(r"\n\s*\n", pre) if x.strip()]
    lede = paras[0] if paras else ""
    meta = paras[1] if len(paras) > 1 else ""
    secs, order = sections(md)
    attached = []  # Dimensions shown in the figures section instead of as cards

    out = {}
    # glance
    if "glance" in secs:
        head, body = secs["glance"]
        items = []
        for b in bullets(body):
            m = re.match(r"^\*\*(.+?)\*\*:\s*(.+?)\s+[—–]\s+(.+)$", b)
            if not m:
                problems.append(f"SHORT {head}: '{b[:60]}' is not '**label**: figure — text'")
                continue
            items.append(f'<div class="fig"><h3 class="lab">{inline(m.group(1))}</h3>'
                         f'<div class="big">{nobreak(inline(m.group(2)))}</div><p>{inline(m.group(3))}</p></div>')
        if len(items) != 4:
            problems.append(f"SHORT {head}: {len(items)} items; the template asks for four")
        out["glance"] = (f'<section id="glance" aria-labelledby="h-glance"><h2 id="h-glance" class="vh">{esc(head)}</h2>'
                         f'<div class="figs">{"".join(items)}</div></section>')
    # key figures
    if "figures" in secs:
        head, body = secs["figures"]
        lead = body.split("\n### ", 1)[0]
        h = f'<section id="figures"><h2>{esc(head)}</h2>' + "".join(
            f'<p class="sub">{inline(x)}</p>' for x in re.split(r"\n\s*\n", lead) if x.strip())
        deep_dims = []
        for m in re.finditer(r"^### (.+?)\n(.*?)(?=^### |\Z)", body, re.S | re.M):
            fid, fl = m.group(1).strip(), fields(m.group(2))
            f, spec = use_fig(fid, head)
            if fl.get("Dimension"):
                deep_dims.append(fl["Dimension"])
            if not f:
                continue
            pins = pinned_sides(spec)
            notes = "".join(note(s, fl[k], s in pins) for s, k in (("PRO", "Pro"), ("CON", "Con")) if fl.get(k))
            if fl.get("Pro") and fl.get("Con"):
                check_card_balance(f"{head} / {fid}", fl["Pro"], fl["Con"])
            h += (f'<div class="story{"" if notes else " single"}">{figure_block(f, spec)}'
                  + (f'<aside class="pins">{notes}</aside>' if notes else "") + "</div>")
        for d in deep_dims:
            if d not in rdims:
                problems.append(f"SHORT {head}: Dimension '{d}' is not a '### ' heading in Section 2 of {rp.name}")
                continue
            attached.append(d)
            h += f'<div class="deep-solo" id="d-{slug(d)}">' + details(deep_panel(d, rdims, {}, sfx, has_conf, "h3"), d) + "</div>"
        out["figures"] = h + "</section>"
    # dimension cards (read before the strength section, which links to them)
    cards = []
    if "dimensions" in secs:
        head, body = secs["dimensions"]
        lead = body.split("\n### ", 1)[0]
        for m in re.finditer(r"^### (.+?)\n(.*?)(?=^### |\Z)", body, re.S | re.M):
            cards.append(dict(fields(m.group(2)), dim=m.group(1).strip()))
    card_dims = [c["dim"] for c in cards]
    for d in card_dims:
        if rdims and d not in rdims:
            problems.append(f"SHORT card '{d}': not a '### ' heading in Section 2 of {rp.name}")
        if card_dims.count(d) > 1:
            problems.append(f"SHORT card '{d}': appears {card_dims.count(d)} times")
    for d in rdims:
        if d not in card_dims and d not in attached:
            problems.append(f"SHORT: Dimension '{d}' has no card and is not attached to the figures section")
    anchor = {d: f"d-{slug(d)}" for d in card_dims + attached}
    # strength + unit chart
    if "strength" in secs:
        head, body = secs["strength"]
        fl = fields(body)
        rest = FIELD_RE.sub("", body)
        lead = [x.strip() for x in re.split(r"\n\s*\n", rest) if x.strip() and not x.strip().startswith(("-", "*"))]
        qs = []
        for d, parts in rdims.items():
            for b in parts.get("Open questions", []):
                s = re.search(R.STATUS_MARK, b)
                if s:
                    q = re.match(r"^\*\*(.+?)\*\*", b)
                    qs.append((R.STATUS_WORDS[s.group(1)], q.group(1) if q else b[:80], d))
        n = len(qs)
        groups = ""
        if n:
            opn = [q for q in qs if q[0] == "unsettled"]
            groups += (f'<div class="ugroup open"><div class="uhead"><b>{len(opn)}</b> {esc(S["groups"]["unsettled"])}</div>'
                       f'<div class="ucells">' + '<i class="u open"></i>' * len(opn) + "</div></div>")
            for st in ("settled", "leaning Pro", "leaning Con"):
                g = [q for q in qs if q[0] == st]
                if not g:
                    continue
                items = "".join(f'<li><i class="u {CHIP_CLASS[st]}" aria-hidden="true"></i>'
                                + (f'<a href="#{anchor[d]}">{inline(q, False)}</a>' if d in anchor else inline(q, False)) + "</li>"
                                for _, q, d in g)
                groups += (f'<div class="ugroup"><div class="uhead"><b>{len(g)}</b> {esc(S["groups"][st])}</div>'
                           f'<ul class="uq">{items}</ul></div>')
        counts = ", ".join(f'{sum(1 for q in qs if q[0] == st)} {S["groups"][st]}' for st in ("settled", "leaning Pro", "leaning Con", "unsettled"))
        units = (f'<figure class="units" aria-label="{esc(S["status_title"].format(n=n))}: {esc(counts)}">'
                 f'<figcaption><b>{esc(S["status_title"].format(n=n))}</b></figcaption><div class="urow">{groups}</div></figure>') if n else ""
        cols = ""
        for s, k in (("PRO", "Pro"), ("CON", "Con")):
            if not fl.get(k):
                problems.append(f"SHORT {head}: no **{k}** list")
            cols += (f'<div class="col {"za" if s == "PRO" else "proti"}"><h3>{esc(S["stronger"][s])}</h3><ul>'
                     + "".join(f"<li>{inline(b)}</li>" for b in bullets(fl.get(k, ""))) + "</ul></div>")
        sub = f'<p class="sub">{inline(lead[0])}</p>' if lead else ""
        fine = "".join(f'<p class="fine">{inline(x)}</p>' for x in lead[1:])
        out["strength"] = f'<section id="strength"><h2>{esc(head)}</h2>{sub}{units}<div class="pair">{cols}</div>{fine}</section>'
    # dimensions
    if "dimensions" in secs:
        head, body = secs["dimensions"]
        lead = [x.strip() for x in re.split(r"\n\s*\n", body.split("\n### ", 1)[0]) if x.strip()]
        top = scale_max(cards)
        h = (f'<section id="dimensions"><h2>{esc(head)}</h2>' + "".join(f'<p class="sub">{inline(x)}</p>' for x in lead)
             + f'<div class="toolbar"><button type="button" class="openall" id="openAll" aria-pressed="false"'
               f' data-open-label="{esc(S["open_all"])}" data-close-label="{esc(S["close_all"])}">{esc(S["open_all"])}</button></div>')
        group = None
        for c in cards:
            d = c["dim"]
            for k in ("Changes", "Pro", "Con"):
                if not c.get(k):
                    problems.append(f"SHORT card '{d}': no **{k}**")
            if c.get("Pro") and c.get("Con"):
                check_card_balance(f"card '{d}'", c["Pro"], c["Con"])
            sides = [SIDE_WORDS[t[0].lower()] for t in TURN_RE.findall(c.get("Exchange", ""))]
            if sides and abs(sides.count("PRO") - sides.count("CON")) > 1:
                problems.append(f"BALANCE card '{d}': Exchange has {sides.count('PRO')} Pro and {sides.count('CON')} Con turns")
            bad = [ln for ln in bullets(c.get("Exchange", "")) if not TURN_RE.match("- " + ln)]
            for ln in bad:
                problems.append(f"SHORT card '{d}': Exchange line '{ln[:50]}' is not '- **<Side> · <Stage>**: text'")
            if c.get("Group") and c["Group"] != group:
                group = c["Group"]
                h += f'<div class="group-h"><h3>{inline(group)}</h3></div>'
            spec, fig = None, ""
            if c.get("Figure"):
                f, spec = use_fig(c["Figure"], f"card '{d}'")
                if f:
                    fig = figure_block(f, spec)
            pins = pinned_sides(spec)
            name = c.get("Name") or d
            prov = f'<span class="art">{inline(c["Provisions"])}</span>' if c.get("Provisions") else ""
            meta_col = f'<h3>{inline(name)}{prov}</h3>' + (scale_html(c["Scale"], top) if c.get("Scale") else "")
            main = f'<p class="what">{inline(c.get("Changes", ""))}</p>' + fig
            if c.get("Key fact"):
                main += f'<p class="fact">{inline(c["Key fact"])}</p>'
            if c.get("Key question"):
                kq = c["Key question"]
                m = re.match(r"^(.*?)\s*" + R.STATUS_MARK + r"\s*[—–-]?\s*(.*)$", kq, re.S)
                if m:
                    main += (f'<div class="q"><div><span class="qq">{inline(m.group(1))}</span>{chip(R.STATUS_WORDS[m.group(2)])}</div>'
                             + (f'<p class="qa">{inline(m.group(3))}</p>' if m.group(3).strip() else "") + "</div>")
                else:
                    problems.append(f"SHORT card '{d}': Key question has no '· Status: …' marker")
                    main += f'<div class="q"><div><span class="qq">{inline(kq)}</span></div></div>'
            notes = "".join(note(s, c[k], s in pins) for s, k in (("PRO", "Pro"), ("CON", "Con")) if c.get(k))
            h += (f'<article class="m" id="d-{slug(d)}"><div class="m-meta">{meta_col}</div><div class="m-main">{main}</div>'
                  f'<div class="m-notes">{notes}</div>{details(deep_panel(d, rdims, c, sfx, has_conf))}</article>')
        out["dimensions"] = h + "</section>"
    # values
    if "values" in secs:
        head, body = secs["values"]
        rows = [r for r in re.findall(r"^\|(.+)\|\s*$", body, re.M)]
        cells = [[x.strip() for x in r.split("|")] for r in rows]
        cells = [r for r in cells if not all(re.fullmatch(r":?-{3,}:?", x) for x in r)]
        lead = [x.strip() for x in re.split(r"\n\s*\n", body) if x.strip() and not x.strip().startswith("|")]
        if not cells or any(len(r) != 3 for r in cells):
            problems.append(f"SHORT {head}: the table needs three columns: Pro | area | Con")
            cells = [r for r in cells if len(r) == 3]
        thead, tbody = (cells[0], cells[1:]) if cells else (["", "", ""], [])
        trs = "".join(f'<tr><td class="za">{inline(z)}</td><th class="topic" scope="row">{inline(t)}</th><td class="proti">{inline(p)}</td></tr>'
                      for z, t, p in tbody)
        out["values"] = (f'<section id="values"><h2>{esc(head)}</h2>' + "".join(f'<p class="sub">{inline(x)}</p>' for x in lead)
                         + f'<table class="values"><thead><tr><th class="za" scope="col">{inline(thead[0])}</th>'
                           f'<th class="topic" scope="col">{inline(thead[1])}</th><th class="proti" scope="col">{inline(thead[2])}</th></tr></thead>'
                           f'<tbody>{trs}</tbody></table></section>')
    # unknowns
    if "unknowns" in secs:
        head, body = secs["unknowns"]
        items = re.findall(r"^\s*\d+\.\s+(.+)$", body, re.M)
        lead = [x.strip() for x in re.split(r"\n\s*\n", body) if x.strip() and not re.match(r"\d+\.", x.strip())]
        lis = ""
        for it in items:
            m = re.match(r"^\*\*(.+?)\*\*:?\s*(.*)$", it)
            lis += (f"<li><b>{inline(m.group(1))}</b><span>{inline(m.group(2))}</span></li>" if m else f"<li><span>{inline(it)}</span></li>")
        out["unknowns"] = (f'<section id="unknowns"><h2>{esc(head)}</h2>' + "".join(f'<p class="sub">{inline(x)}</p>' for x in lead)
                           + f'<ol class="unknown">{lis}</ol></section>')

    main_html = "\n".join(out[k] for k in order if k in out)
    nav = "".join(f'<a href="#{k}">{esc(secs[k][0])}</a>' for k in order if k in out)
    brand = title.split(":", 1)[0] if ":" in title and len(title.split(":", 1)[0]) <= 30 else S["brand"]
    sub = f' <span>{esc(S["brand"].lower())}</span>' if brand != S["brand"] else ""
    first = next((k for k in order if k in out), "glance")

    # Evidence the page cites: checked, then embedded for the source panel
    cited = sorted(set(re.findall(rf"evidence/({R.EID})\.md", main_html)))
    for i in cited:
        if i not in ev:
            problems.append(f"SHORT: {i} is cited but has no Evidence file")
        elif ev[i]["audit"] == "failed":
            problems.append(f"SHORT: {i} failed the Audit; take it out")
        elif ev[i]["audit"] == "not audited":
            problems.append(f"SHORT: {i} was never audited")
    keep = {}
    for i in cited:
        if i in ev:
            e = ev[i]
            q = e["quote"] if len(e["quote"]) <= 1500 else e["quote"][:1500].rsplit(" ", 1)[0] + " …"
            keep[i] = {"title": e["title"], "publisher": e["publisher"], "published": e["published"], "url": e["url"],
                       "quote": q, "translation": e["translation"][:1500], "tier": e["tier"], "audit": e["audit"],
                       "cherry": e["cherry"]}
    ui = dict(S["drawer"], closer_pro=S["closer"]["PRO"], closer_con=S["closer"]["CON"], tiers=R.STRINGS[code]["tier_names"], dec="," if code == "sl" else ".",
              thou="." if code == "sl" else ",", evdir=R.EVDIR)
    jdump = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")  # noqa: E731
    css = (ASSETS / "fonts.css").read_text(encoding="utf-8") + CSS
    page = f"""<!doctype html>
<html lang="{esc(code)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title[:100])}</title>
<style>{css}</style>
</head>
<body>
<a class="skip" href="#{first}">{esc(S["skip"])}</a>
<nav class="toc" aria-label="{esc(S["nav"])}"><div class="toc-in">
<a class="brand" href="#top">{esc(brand)}{sub}</a>
<div class="toc-links">{nav}</div>
</div></nav>
<header class="top" id="top">
<h1>{inline(title, False)}</h1>
<p class="lede">{inline(lede)}</p>
<div class="meta">{inline(meta)} · {esc(S["full_text"])} <a href="report{sfx}.html">{esc(S["full"])}</a><span class="hint">{esc(S["hint"])}</span></div>
<p class="notice">{esc(S["notice"])}</p>
</header>
<main>
{main_html}
</main>
<footer><p>{esc(S["footer"])} <a href="report{sfx}.html#methodology">{esc(S["method"])}</a>.</p></footer>
<dialog class="drawer" id="evd" aria-labelledby="evdTitle"><div class="dr-in" id="evdIn"></div></dialog>
<script type="application/json" id="evdata">{jdump(keep)}</script>
<script type="application/json" id="figdata">{jdump(shown)}</script>
<script type="application/json" id="uidata">{jdump(ui)}</script>
<script>{JS}</script>
</body>
</html>
"""
    outp = outdir / f"report-short{sfx}.html"
    outp.write_text(page, encoding="utf-8")
    return outp, len(shown), len(keep)


def main(args):
    lang = None
    if "--lang" in args:
        i = args.index("--lang")
        lang = args[i + 1].lower()
        del args[i:i + 2]
    folder, outdir = R.layout(Path(args[0]))
    R.EVDIR = urllib.parse.quote(os.path.relpath(folder / "evidence", outdir))
    _, _, report_lang = R.read_motion(folder, lang)
    code = lang or R.LANG_NAMES.get(report_lang.lower(), "en" if not report_lang else None)
    if code not in SUI:
        problems.append(f"LANG {lang or report_lang}: no interface strings for the short report; using English")
        code = "en"
    R.UI = R.STRINGS.get(code, R.STRINGS["en"])
    res = build(folder, outdir, lang, code)
    for p in R.problems + problems:
        print(p)
    if res:
        outp, nf, ne = res
        print(f"{outp.name} written: {nf} figures, {ne} Evidence embedded")


CSS = r"""
:root{
  --bg:#fbfbfa;--paper:#fff;--ink:#1c1c1e;--ink-2:#45454a;--ink-3:#66666b;--line:#dcd9d2;--line-2:#ecebe7;
  --data:#c9c6bf;--data-mid:#8f8b84;--data-strong:#1c1c1e;--on-data:#fff;
  --za:#0f6b78;--proti:#7b3f8c;
  --sans:"Schibsted Grotesk",ui-sans-serif,system-ui,"Segoe UI",Roboto,Arial,sans-serif;
  --serif:"Literata",Georgia,"Times New Roman",serif;
  --col:680px;--page:1180px;--gut:clamp(16px,4vw,48px);color-scheme:light;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#141416;--paper:#1b1b1e;--ink:#ecebe8;--ink-2:#c4c3c0;--ink-3:#9c9ca1;--line:#34343a;--line-2:#26262a;
  --data:#55555c;--data-mid:#86868d;--data-strong:#ecebe8;--on-data:#141416;--za:#62c3cf;--proti:#cc9be3;color-scheme:dark;
}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:64px}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.65 var(--serif);font-variant-numeric:lining-nums;-webkit-font-smoothing:antialiased}
:focus-visible{outline:2px solid var(--ink);outline-offset:3px;border-radius:2px}
a{color:inherit;text-decoration-color:var(--ink-3);text-underline-offset:.2em;text-decoration-thickness:1px}
a:hover{text-decoration-color:var(--ink);text-decoration-thickness:2px}
h1,h2,h3,h4{font-family:var(--sans);text-wrap:balance;margin:0}
p,li{text-wrap:pretty}
b,strong{font-weight:650}
.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.skip{position:absolute;left:-999px;top:8px;background:var(--ink);color:var(--bg);padding:8px 12px;font:600 14px var(--sans);z-index:20}
.skip:focus{left:8px}
nav.toc{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--bg) 94%,transparent);backdrop-filter:saturate(1.2) blur(8px);border-bottom:1px solid var(--line)}
.toc-in{max-width:var(--page);margin:0 auto;padding:0 var(--gut);display:flex;align-items:center;gap:28px;height:52px}
.brand{font:800 15px var(--sans);text-decoration:none;white-space:nowrap;letter-spacing:-.01em}
.brand span{font-weight:400;color:var(--ink-3)}
.toc-links{display:flex;gap:22px;overflow-x:auto;scrollbar-width:none;height:100%;align-items:stretch}
.toc-links::-webkit-scrollbar{display:none}
.toc-links a{display:flex;align-items:center;font:500 14px var(--sans);color:var(--ink-3);text-decoration:none;white-space:nowrap;border-bottom:2px solid transparent;margin-bottom:-1px}
.toc-links a:hover{color:var(--ink)}
.toc-links a[aria-current="true"]{color:var(--ink);border-bottom-color:var(--ink)}
@media (max-width:760px){.brand span{display:none}.toc-in{gap:16px}.toc-links{-webkit-mask-image:linear-gradient(90deg,#000 85%,transparent);mask-image:linear-gradient(90deg,#000 85%,transparent);padding-right:24px}}
header.top,main>section,footer{max-width:var(--page);margin:0 auto;padding-left:var(--gut);padding-right:var(--gut)}
header.top{padding-top:clamp(28px,4.5vw,56px)}
h1{font-weight:800;font-size:clamp(32px,4.8vw,58px);line-height:1.04;letter-spacing:-.028em;max-width:24ch}
.lede{font-size:clamp(18px,1.8vw,21px);line-height:1.5;color:var(--ink-2);max-width:var(--col);margin:20px 0 0}
.meta{font:400 14px/1.6 var(--sans);color:var(--ink-3);margin-top:20px;max-width:var(--col)}
.meta .hint{display:block}
.notice{font:400 15.5px/1.55 var(--serif);color:var(--ink-2);max-width:var(--col);margin:14px 0 0;padding-top:14px;border-top:1px solid var(--line)}
main>section{padding-top:clamp(56px,8vw,104px)}
main>section#glance{padding-top:clamp(36px,5vw,56px)}
h2{font-weight:800;font-size:clamp(26px,3vw,36px);line-height:1.1;letter-spacing:-.02em;max-width:24ch}
.sub{color:var(--ink-2);max-width:var(--col);margin:12px 0 0}
.figs{display:grid;grid-template-columns:repeat(4,1fr);border-top:2px solid var(--ink)}
.fig{display:flex;flex-direction:column;padding:18px 22px 4px 0}
.fig+.fig{padding-left:22px;border-left:1px solid var(--line)}
.fig .big{order:-1;font:800 clamp(24px,2.5vw,32px)/1.08 var(--sans);letter-spacing:-.025em;margin-bottom:10px}
.fig .lab{font:700 15px/1.3 var(--sans);margin:0 0 6px}
.fig p{font-size:15.5px;line-height:1.55;color:var(--ink-2);margin:0 0 8px}
@media (max-width:980px){.figs{grid-template-columns:1fr 1fr}.fig:nth-child(3){padding-left:0;border-left:0}.fig:nth-child(n+3){border-top:1px solid var(--line);margin-top:8px}}
@media (max-width:560px){.figs{grid-template-columns:1fr}.fig,.fig+.fig{padding:16px 0 6px;border-left:0}.fig+.fig{border-top:1px solid var(--line)}}
.chip{display:inline-flex;align-items:center;gap:6px;font:600 13px/1.3 var(--sans);white-space:nowrap;color:var(--ink-2);vertical-align:1px}
.chip::before{content:"";width:10px;height:10px;flex:none}
.chip.settled::before{border-radius:50%;background:var(--ink)}
.chip.za{color:var(--za)}.chip.za::before{background:var(--za)}
.chip.proti{color:var(--proti)}.chip.proti::before{background:var(--proti);clip-path:polygon(50% 0,100% 100%,0 100%);width:11px;height:11px}
.chip.open::before{border-radius:50%;box-shadow:inset 0 0 0 1.5px var(--ink-3)}
figure{margin:0}
.units{margin-top:32px}
.units figcaption,.fig-chart figcaption{font:700 16px var(--sans);display:flex;flex-wrap:wrap;gap:6px 18px;align-items:baseline}
.fig-chart figcaption .unit{font-weight:400;font-size:14px;color:var(--ink-3)}
.urow{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:22px 36px;margin-top:16px}
.ugroup.open{grid-column:1/-1}
.uq{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px}
.uq li{display:grid;grid-template-columns:22px 1fr;gap:10px;align-items:start;font:500 15px/1.4 var(--sans)}
.uq a{text-decoration:none}.uq a:hover{text-decoration:underline}
.ugroup .uhead{font:400 14px var(--sans);color:var(--ink-2);margin-bottom:8px}
.ugroup .uhead b{font-size:22px;font-weight:800;color:var(--ink);margin-right:4px;letter-spacing:-.02em}
.ucells{display:flex;flex-wrap:wrap;gap:5px}
.u{display:block;width:22px;height:22px}
.u.settled{background:var(--ink);border-radius:50%}
.u.za{background:var(--za)}
.u.proti{background:var(--proti);clip-path:polygon(50% 0,100% 100%,0 100%)}
.u.open{border-radius:50%;box-shadow:inset 0 0 0 1.5px var(--ink-3)}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:0 48px;margin-top:40px}
.pair .col{border-top:3px solid}
.pair .col.za{border-color:var(--za)}.pair .col.proti{border-color:var(--proti)}
.pair h3{font:700 18px var(--sans);padding:12px 0 6px}
.pair .za h3{color:var(--za)}.pair .proti h3{color:var(--proti)}
.pair ul{list-style:none;margin:0;padding:0}
.pair li{font-size:16px;line-height:1.55;padding:12px 0;border-bottom:1px solid var(--line-2)}
.pair li b{font-family:var(--sans);font-weight:700;font-size:15.5px}
@media (max-width:760px){.pair{grid-template-columns:1fr;gap:28px}}
.fine{font:400 15px/1.55 var(--sans);color:var(--ink-3);max-width:var(--col);margin:18px 0 0}
.chart{width:100%;margin-top:10px}
.chart svg{display:block;width:100%;height:auto;overflow:visible}
.chart text{fill:var(--ink-2);font:400 13px var(--sans)}
.chart .val{fill:var(--ink);font-weight:700}
.chart .lbl{fill:var(--ink)}
.chart-cap{font:400 14px/1.55 var(--sans);color:var(--ink-3);margin:10px 0 0;max-width:var(--col)}
.fig-src{font:400 13px/1.6 var(--sans);color:var(--ink-3);margin:6px 0 0}
.legend{display:inline-flex;flex-wrap:wrap;gap:4px 16px;font:400 13.5px var(--sans);color:var(--ink-2)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.k{display:inline-block;width:12px;height:12px}
.k.s1{background:var(--data-strong)}.k.s2{background:var(--data)}.k.s3{background:var(--data-mid)}
.story{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:40px;margin-top:40px;align-items:start}
.story.single{grid-template-columns:minmax(0,760px)}
.pins{padding-top:30px;display:flex;flex-direction:column;gap:22px}
@media (max-width:900px){.story{grid-template-columns:1fr;gap:18px}.pins{padding-top:0}}
.note{position:relative;font-size:15.5px;line-height:1.55;padding:10px 0 0;border-top:3px solid}
.note>b:first-of-type{display:block;font:700 13px var(--sans);letter-spacing:.06em;text-transform:uppercase;margin-bottom:4px}
.note.za{border-color:var(--za)}.note.za>b:first-of-type{color:var(--za)}
.note.proti{border-color:var(--proti)}.note.proti>b:first-of-type{color:var(--proti)}
.pin{float:right;display:inline-grid;place-items:center;width:22px;height:22px;border-radius:50%;font:700 12px var(--sans);color:var(--on-data);margin:-1px 0 4px 8px}
.note.za .pin{background:var(--za)}.note.proti .pin{background:var(--proti)}
.group-h{display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 14px;margin:64px 0 0;padding-bottom:10px;border-bottom:2px solid var(--ink)}
.group-h h3{font:800 22px var(--sans);letter-spacing:-.015em}
.toolbar{margin-top:20px}
.openall{font:600 14px var(--sans);color:var(--ink);background:none;border:1px solid var(--line);padding:8px 14px;cursor:pointer;min-height:40px}
.openall:hover{border-color:var(--ink)}
article.m{display:grid;grid-template-columns:200px minmax(0,1fr) 280px;gap:0 40px;padding:32px 0 28px;border-bottom:1px solid var(--line)}
.m-meta h3{font:800 20px/1.2 var(--sans);letter-spacing:-.015em}
.m-meta .art{display:block;font:400 13.5px var(--sans);color:var(--ink-3);margin-top:4px;letter-spacing:0}
.mc{margin-top:14px}
.mc-row{display:grid;grid-template-columns:minmax(24px,auto) 1fr auto;align-items:center;gap:8px;font:600 12px var(--sans);color:var(--ink-3);height:20px}
.mc-row i{display:block;height:9px;width:var(--w);background:var(--data-strong);min-width:2px}
.mc-row.mf i{background:var(--data)}
.mc-row b{font:700 13px var(--sans);color:var(--ink);font-variant-numeric:tabular-nums}
.mc-u{font:400 12px/1.4 var(--sans);color:var(--ink-3);margin-top:4px}
.mc-none{font:400 13px/1.4 var(--sans);color:var(--ink-3);margin:12px 0 0}
.m-main>*{margin:0}
.m-main>*+*{margin-top:16px}
.what{font-size:17px}
.fact{font-size:16px;color:var(--ink-2);padding-left:14px;border-left:1px solid var(--ink)}
.m-notes{display:flex;flex-direction:column;gap:22px}
.q{font-family:var(--sans);padding-top:14px;border-top:1px solid var(--line-2)}
.q>div{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:baseline}
.q .qq{font:700 16px/1.4 var(--sans)}
.q .qa{font:400 15px/1.55 var(--serif);color:var(--ink-2);margin:6px 0 0}
@media (max-width:1060px){
  article.m{grid-template-columns:180px minmax(0,1fr);gap:0 32px}
  .m-notes{grid-column:2;flex-direction:row;gap:24px;margin-top:22px}.m-notes .note{flex:1}
}
@media (max-width:700px){
  article.m{grid-template-columns:1fr}
  .m-meta{display:grid;grid-template-columns:1fr 132px;gap:0 16px;align-items:start;margin-bottom:16px}
  .mc,.mc-none{margin-top:2px}
  .m-notes{grid-column:1;flex-direction:column;gap:18px}
}
details.deep{grid-column:2/-1;margin-top:22px;border-top:1px solid var(--line-2)}
.deep-solo details.deep{margin-top:40px;border-top:1px solid var(--line)}
details.deep>summary{cursor:pointer;list-style:none;display:flex;flex-wrap:wrap;white-space:nowrap;align-items:center;gap:2px 10px;padding:12px 0;font:700 15px var(--sans);color:var(--ink)}
details.deep>summary::-webkit-details-marker{display:none}
details.deep>summary::before{content:"";width:8px;height:8px;border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:translateY(-2px) rotate(45deg);transition:transform .2s cubic-bezier(.16,1,.3,1);flex:none}
details.deep[open]>summary::before{transform:translateY(2px) rotate(-135deg)}
details.deep>summary .sum-sub{font-weight:400;color:var(--ink-3);white-space:normal}
details.deep>summary:hover{text-decoration:underline;text-underline-offset:.25em}
details.deep[open]>.deep-body{animation:deepIn .3s cubic-bezier(.16,1,.3,1)}
@keyframes deepIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){details.deep[open]>.deep-body{animation:none}details.deep>summary::before{transition:none}}
.deep-body{max-width:860px;padding-bottom:8px}
.deep-body h4,.deep-body h3{font:700 13px var(--sans);letter-spacing:.05em;text-transform:uppercase;color:var(--ink-3);margin:22px 0 8px}
.deep-body .h5note{text-transform:none;letter-spacing:0;font-weight:400}
.deep-body ul{margin:0;padding-left:18px}
.deep-body li{font-size:15.5px;line-height:1.6;margin:0 0 8px;color:var(--ink-2)}
.deep-body li::marker{color:var(--ink-3)}
.deep-body .args{display:grid;grid-template-columns:1fr 1fr;gap:28px}
.deep-body .arg{border-top:3px solid;padding-top:8px}
.deep-body .arg.za{border-color:var(--za)}.deep-body .arg.proti{border-color:var(--proti)}
.deep-body .arg>b{display:block;font:700 13px var(--sans);letter-spacing:.05em;text-transform:uppercase;margin-bottom:6px}
.deep-body .arg.za>b{color:var(--za)}.deep-body .arg.proti>b{color:var(--proti)}
.deep-body .arg li{color:var(--ink);font-size:15px}
.chat{display:grid;grid-template-columns:1fr 1fr;gap:12px 28px}
.bub{font-size:15px;line-height:1.55;padding-top:8px;border-top:1px solid}
.bub .who{display:block;font:700 12px var(--sans);letter-spacing:.05em;text-transform:uppercase;margin-bottom:3px}
.bub.za{grid-column:1;border-color:var(--za)}.bub.za .who{color:var(--za)}
.bub.proti{grid-column:2;border-color:var(--proti)}.bub.proti .who{color:var(--proti)}
.deeplinks{display:flex;flex-wrap:wrap;gap:8px 24px;margin:20px 0 0;font:600 14.5px var(--sans)}
@media (max-width:1060px) and (min-width:701px){details.deep{grid-column:2}}
@media (max-width:700px){details.deep{grid-column:1}details.deep>summary .sum-sub{flex-basis:100%;padding-left:18px;font-size:14px}
  .deep-body .args{grid-template-columns:1fr;gap:18px}.chat{grid-template-columns:1fr}.bub.za,.bub.proti{grid-column:1}.bub.proti{margin-left:24px}}
table.values{width:100%;border-collapse:collapse;margin-top:28px;font-size:16px;line-height:1.5}
table.values thead th{font:700 13px/1.35 var(--sans);letter-spacing:.02em;padding:0 0 10px;vertical-align:bottom;border-bottom:2px solid var(--ink)}
table.values th.za,table.values td.za{text-align:right;width:40%}
table.values th.proti,table.values td.proti{text-align:left;width:40%}
table.values thead th.za{color:var(--za)}table.values thead th.proti{color:var(--proti)}
table.values thead th.topic{text-align:center;color:var(--ink-3)}
table.values tbody th.topic{font:700 14.5px/1.3 var(--sans);text-align:center;padding:14px 18px}
table.values td{padding:14px 0;vertical-align:middle;color:var(--ink-2)}
table.values tbody tr{border-bottom:1px solid var(--line-2)}
table.values td.za{border-right:1px solid var(--za);padding-right:18px}
table.values td.proti{border-left:1px solid var(--proti);padding-left:18px}
@media (max-width:700px){
  table.values thead{display:none}
  table.values,table.values tbody,table.values tr,table.values td,table.values th{display:block;width:100%}
  table.values tbody tr{display:grid;grid-template-columns:1fr 1fr;padding:14px 0}
  table.values tbody th.topic{grid-column:1/-1;text-align:left;padding:0 0 8px}
  table.values td.za,table.values td.proti{text-align:left;padding:2px 12px 0;border:0;font-size:15px}
  table.values td.za{border-left:1px solid var(--za)}
  table.values td.proti{border-left:1px solid var(--proti)}
  table.values td::before{content:attr(data-closer);display:block;font:700 12px var(--sans);letter-spacing:.04em}
  table.values td.za::before{color:var(--za)}table.values td.proti::before{color:var(--proti)}
}
ol.unknown{list-style:none;counter-reset:u;margin:28px 0 0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,440px),1fr));gap:0 48px}
ol.unknown li{counter-increment:u;display:grid;grid-template-columns:44px 1fr;padding:16px 0;border-top:1px solid var(--line)}
ol.unknown li::before{content:counter(u);font:800 26px/1 var(--sans);color:var(--ink-3);grid-row:1/3}
ol.unknown li b{font:700 17px/1.35 var(--sans)}
ol.unknown li span{font-size:15.5px;color:var(--ink-2);margin-top:4px}
.ev{font:500 11.5px var(--sans);color:var(--ink-3);text-decoration:none;white-space:nowrap;border-bottom:1px solid var(--line);padding-bottom:1px;letter-spacing:.01em}
.ev:hover,.ev[aria-expanded="true"]{color:var(--ink);border-color:var(--ink)}
.drawer{position:fixed;z-index:30;inset:0 0 0 auto;width:min(440px,100vw);margin:0;max-height:none;height:100%;border:0;border-left:1px solid var(--line);padding:0;background:var(--paper);color:var(--ink);box-shadow:-24px 0 48px -24px rgba(0,0,0,.25);overflow:auto;animation:drawIn .28s cubic-bezier(.16,1,.3,1)}
@keyframes drawIn{from{transform:translateX(24px);opacity:0}to{transform:none;opacity:1}}
@keyframes sheetIn{from{transform:translateY(24px);opacity:0}to{transform:none;opacity:1}}
@media (max-width:700px){.drawer{inset:auto 0 0 0;width:100vw;height:auto;max-height:78vh;border-left:0;border-top:1px solid var(--line);box-shadow:0 -24px 48px -24px rgba(0,0,0,.3);animation-name:sheetIn}}
@media (prefers-reduced-motion:reduce){.drawer{animation:none}}
.dr-in{padding:20px 24px 28px;font-family:var(--sans)}
.dr-top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding-bottom:12px;border-bottom:2px solid var(--ink)}
.dr-id{font:700 13px var(--sans);letter-spacing:.04em;color:var(--ink-3)}
.dr-x{background:none;border:0;color:var(--ink-2);cursor:pointer;padding:8px;margin:-8px;display:inline-flex}
.dr-x:hover{color:var(--ink)}.dr-x svg{width:18px;height:18px}
.drawer h3{font:800 19px/1.3 var(--sans);margin:16px 0 6px}
.drawer .src{font-size:14px;color:var(--ink-2);margin:0 0 12px}
.drawer .tags{display:flex;flex-wrap:wrap;gap:6px 14px;margin:0 0 14px;font:600 13px var(--sans)}
.drawer .tag.ok{color:var(--za)}.drawer .tag.part{color:var(--proti)}
.drawer .tag::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;background:currentColor;margin-right:6px;vertical-align:1px}
.drawer blockquote{margin:0;padding:0 0 0 14px;border-left:1px solid var(--ink);font:400 15px/1.6 var(--serif);white-space:pre-wrap;color:var(--ink)}
.drawer .tr{font-size:13px;color:var(--ink-3);margin:14px 0 4px;font-weight:600}
.drawer .links{display:flex;flex-direction:column;gap:8px;margin-top:18px;font-size:14.5px;font-weight:600}
.drawer .note2{font-size:13px;color:var(--ink-3);margin-top:16px;line-height:1.5}
footer{margin-top:96px;padding-top:28px;padding-bottom:64px;border-top:2px solid var(--ink);font:400 15px/1.6 var(--sans);color:var(--ink-2)}
footer p{max-width:var(--col)}
@media print{nav.toc,.openall,.skip,.drawer{display:none!important}body{background:#fff;font-size:11pt}article.m,.fig,.story{break-inside:avoid}main>section{padding-top:24px}}
"""

JS = r"""
(function(){
  function J(id){try{return JSON.parse(document.getElementById(id).textContent);}catch(e){return {};}}
  var EV=J('evdata'), FIG=J('figdata'), UI=J('uidata');
  function esc(t){return String(t==null?'':t).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}

  // the section in view, underlined in the sticky menu
  (function(){
    var links=[].slice.call(document.querySelectorAll('.toc-links a')); if(!('IntersectionObserver' in window)) return;
    var map={}; links.forEach(function(a){map[a.getAttribute('href').slice(1)]=a;});
    var io=new IntersectionObserver(function(es){es.forEach(function(e){ if(!e.isIntersecting) return;
      links.forEach(function(a){a.removeAttribute('aria-current');}); var a=map[e.target.id];
      if(a){a.setAttribute('aria-current','true'); var p=a.parentNode; p.scrollLeft=Math.max(0,a.offsetLeft-p.clientWidth/3);} });},{rootMargin:'-40% 0px -55% 0px'});
    Object.keys(map).forEach(function(id){var s=document.getElementById(id); if(s) io.observe(s);});
  })();

  // the values table on a phone: each cell says which Side it is closer to
  document.querySelectorAll('table.values').forEach(function(t){
    var h=t.querySelectorAll('thead th'); t.querySelectorAll('tbody tr').forEach(function(r){
      var c=r.querySelectorAll('td'); if(c[0]) c[0].setAttribute('data-closer',UI.closer_pro||''); if(c[1]) c[1].setAttribute('data-closer',UI.closer_con||'');});
  });

  // ---------- charts ----------
  var NS='http://www.w3.org/2000/svg';
  // a value as the figure gives it (at most two decimals), with the page language's separators
  function nf(v){var p=String(Math.round(Math.abs(v)*100)/100).split('.');
    return (v<0?'−':'')+p[0].replace(/\B(?=(\d{3})+(?!\d))/g,UI.thou)+(p[1]?UI.dec+p[1]:'');}
  function el(tag,attrs,parent,text){var e=document.createElementNS(NS,tag);for(var k in attrs)e.setAttribute(k,attrs[k]);if(text!=null)e.textContent=text;if(parent)parent.appendChild(e);return e;}
  function wrap(s,n){s=String(s); if(s.length<=n) return [s]; var w=s.split(' '), a='', b=''; w.forEach(function(x){ if((a+' '+x).trim().length<=Math.max(n,s.length/2)&&!b) a=(a+' '+x).trim(); else b=(b+' '+x).trim();}); return b?[a,b]:[a];}
  function fitLab(host,labels,W){var t=el('svg',{width:1,height:1,style:'position:absolute;visibility:hidden'},host), m=0;
    labels.forEach(function(ls){ls.forEach(function(l){var x=el('text',{'class':'lbl'},t,l);try{m=Math.max(m,x.getComputedTextLength());}catch(e){}});});
    host.removeChild(t); return Math.min(Math.round(W*0.46),Math.ceil(m)+14);}
  var COL=['var(--data-strong)','var(--data)','var(--data-mid)'];
  function pin(svg,x,y,p){el('circle',{cx:x,cy:y,r:10,fill:p.side==='PRO'?'var(--za)':'var(--proti)'},svg);
    el('text',{x:x,y:y+4.2,'text-anchor':'middle',style:'fill:var(--on-data);font-size:11.5px;font-weight:700'},svg,p.n);}

  function bar(host,f){
    var W=Math.max(280,Math.round(host.clientWidth||600)), cats=f.categories||[], ser=f.series||[], ns=ser.length;
    var labels=cats.map(function(c){return wrap(c,W<460?16:28);}), labW=fitLab(host,labels,W);
    var barH=ns>1?12:18, gap=ns>1?3:0, rowGap=14, pins=f.pins||[], emph=f.emphasis||[];
    var lines=labels.map(function(l){return l.length;});
    var rowH=function(i){return Math.max(ns*barH+(ns-1)*gap,lines[i]*15);};
    var H=cats.reduce(function(s,c,i){return s+rowH(i)+rowGap;},0)-rowGap+4;
    var vals=[]; ser.forEach(function(s){(s.values||[]).forEach(function(v){if(v!=null) vals.push(v);});});
    var hi=Math.max.apply(null,vals.concat([0])), lo=Math.min.apply(null,vals.concat([0])), span=(hi-lo)||1;
    var svg=el('svg',{viewBox:'0 0 '+W+' '+H},host), x1=W-(pins.length?84:56), sx=function(v){return labW+(x1-labW)*(v-lo)/(span*1.08);};
    var x0=sx(0); el('line',{x1:x0,x2:x0,y1:0,y2:H,stroke:'var(--ink)','stroke-width':1},svg);
    var y=0;
    cats.forEach(function(c,i){
      var rh=rowH(i), end=0;
      labels[i].forEach(function(l,j){el('text',{x:labW-10,y:y+rh/2+4.5-(labels[i].length-1)*7.5+j*15,'text-anchor':'end','class':'lbl'},svg,l);});
      var inner=ns*barH+(ns-1)*gap, top=y+(rh-inner)/2;
      ser.forEach(function(s,k){
        var v=(s.values||[])[i]; if(v==null) return;
        var by=top+k*(barH+gap), a=sx(Math.min(0,v)), w=Math.max(1.5,Math.abs(sx(v)-x0));
        var fill=ns>1?COL[Math.min(k,2)]:(emph.indexOf(c)>=0?COL[0]:COL[1]);
        var r=el('rect',{x:a,y:by,width:w,height:barH,fill:fill},svg); el('title',{},r,(s.name?s.name+': ':'')+nf(v)+(f.unit?' '+f.unit:''));
        var t=el('text',{x:a+w+6,y:by+barH/2+4.5,'class':'val',style:'font-size:'+(ns>1?12:13)+'px'},svg,nf(v));
        var tw=0; try{tw=t.getComputedTextLength();}catch(e){} end=Math.max(end,a+w+6+tw);
      });
      pins.filter(function(p){return p.at===c;}).forEach(function(p,j){pin(svg,Math.min(W-11,end+17+j*24),y+rh/2,p);});
      y+=rh+rowGap;
    });
  }

  function ticks(lo,hi,n){var span=hi-lo||1, step=Math.pow(10,Math.floor(Math.log10(span/n))), e=span/n/step;
    step*=e>=5?5:e>=2?2:1; var out=[]; for(var v=Math.ceil(lo/step)*step; v<=hi+1e-9; v+=step) out.push(Math.round(v*1e6)/1e6); return out;}

  function line(host,f){
    var W=Math.max(280,Math.round(host.clientWidth||600)), narrow=W<460, ser=f.series||[], pins=f.pins||[];
    var pts=[]; ser.forEach(function(s){(s.points||[]).forEach(function(p){pts.push(p);});}); pins.forEach(function(p){pts.push(p.at);});
    if(!pts.length) return;
    var xs=pts.map(function(p){return p[0];}), ys=pts.map(function(p){return p[1];});
    var xl=Math.min.apply(null,xs), xh=Math.max.apply(null,xs), yl=Math.min(0,Math.min.apply(null,ys)), yh=Math.max.apply(null,ys)*1.08;
    var H=narrow?210:240, l=52, r=narrow?16:126, t=14, b=f.x_label?42:26;
    var svg=el('svg',{viewBox:'0 0 '+W+' '+H},host);
    var sx=function(v){return l+(W-l-r)*(v-xl)/((xh-xl)||1);}, sy=function(v){return t+(H-t-b)*(1-(v-yl)/((yh-yl)||1));};
    ticks(yl,yh,4).forEach(function(v){el('line',{x1:l,x2:W-r,y1:sy(v),y2:sy(v),stroke:v?'var(--line)':'var(--ink)'},svg);el('text',{x:l-8,y:sy(v)+4,'text-anchor':'end'},svg,nf(v));});
    ticks(xl,xh,Math.max(2,Math.floor((W-l-r)/90))).forEach(function(v){el('text',{x:sx(v),y:H-b+18,'text-anchor':'middle'},svg,nf(v));});
    if(f.x_label) el('text',{x:l,y:H-2,style:'font-size:12px;fill:var(--ink-3)'},svg,f.x_label+(f.y_label?' → '+f.y_label:''));
    ser.forEach(function(s,k){
      var P=(s.points||[]).slice().sort(function(a,b){return a[0]-b[0];}), d=[];
      P.forEach(function(p,i){ if(s.step&&i) d.push([p[0],P[i-1][1]]); d.push(p);});
      el('polyline',{points:d.map(function(p){return sx(p[0])+','+sy(p[1]);}).join(' '),fill:'none',stroke:k?'var(--ink-3)':'var(--data-strong)','stroke-width':k?2:3,'stroke-dasharray':k?'5 4':'','stroke-linejoin':'round'},svg);
      var last=P[P.length-1]; if(!last) return;
      if(narrow) el('text',{x:sx(last[0]),y:sy(last[1])-10,'text-anchor':'end',style:'font-weight:'+(k?600:700)+';fill:var('+(k?'--ink-3':'--ink')+')'},svg,s.name||'');
      else el('text',{x:sx(last[0])+8,y:sy(last[1])+4,style:'font-weight:'+(k?600:700)+';fill:var('+(k?'--ink-3':'--ink')+')'},svg,s.name||'');
    });
    pins.forEach(function(p){pin(svg,sx(p.at[0])+(p.side==='PRO'?4:18),sy(p.at[1])+(p.side==='PRO'?-18:18),p);});
  }

  function draw(){document.querySelectorAll('.chart[data-fig]').forEach(function(h){
    var f=FIG[h.getAttribute('data-fig')]; if(!f) return; h.textContent='';
    if(f.type==='line') line(h,f); else bar(h,f);});}
  var lastW=document.documentElement.clientWidth, tmr;
  draw(); if(document.fonts&&document.fonts.ready) document.fonts.ready.then(draw);
  window.addEventListener('resize',function(){clearTimeout(tmr);tmr=setTimeout(function(){var w=document.documentElement.clientWidth; if(w!==lastW){lastW=w;draw();}},150);});

  // ---------- the source panel: beside the page on a desktop, a bottom sheet on a phone ----------
  var dlg=document.getElementById('evd'), box=document.getElementById('evdIn'), opener=null;
  function close(){ if(!dlg.open) return; dlg.close(); if(opener){opener.setAttribute('aria-expanded','false'); opener.focus(); opener=null;} }
  document.addEventListener('click',function(e){
    var a=e.target.closest&&e.target.closest('a.ev'); if(!a) return;
    var m=(a.getAttribute('href')||'').match(/(E-[A-Z0-9-]+)\.md$/); if(!m||!EV[m[1]]||!dlg.show) return;
    e.preventDefault(); var d=EV[m[1]];
    if(opener) opener.setAttribute('aria-expanded','false');
    opener=a; a.setAttribute('aria-expanded','true');
    var cls=d.audit==='passed'?'ok':(d.audit==='partial'?'part':'');
    var tags='<span class="tag">'+esc((UI.tiers||{})[d.tier]||d.tier)+'</span><span class="tag '+cls+'">'+esc(UI[d.audit]||d.audit)+'</span>'+
      ((d.cherry&&/^(yes|da)/i.test(d.cherry))?'<span class="tag part">'+esc(UI.cherry)+'</span>':'');
    box.innerHTML='<div class="dr-top"><span class="dr-id">'+esc(UI.source)+' '+m[1]+'</span><button class="dr-x" type="button" aria-label="'+esc(UI.close)+'"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"/></svg></button></div>'+
      '<h3 id="evdTitle">'+esc(d.title)+'</h3><p class="src">'+esc(d.publisher)+(d.published?' · '+esc(d.published):'')+'</p>'+
      '<div class="tags">'+tags+'</div><blockquote>'+esc(d.quote)+'</blockquote>'+
      (d.translation?'<p class="tr">'+esc(UI.translation)+'</p><blockquote>'+esc(d.translation)+'</blockquote>':'')+
      '<div class="links">'+(d.url?'<a href="'+esc(d.url)+'" target="_blank" rel="noopener">'+esc(UI.open)+'</a>':'')+
      '<a href="'+esc(a.getAttribute('href'))+'">'+esc(UI.file)+'</a></div><p class="note2">'+esc(UI.note)+'</p>';
    if(dlg.open) dlg.close(); dlg.show(); dlg.scrollTop=0; var x=box.querySelector('.dr-x'); if(x) x.focus();
  });
  dlg.addEventListener('click',function(e){ if(e.target.closest('.dr-x')) close(); });
  document.addEventListener('keydown',function(e){ if(e.key==='Escape') close(); });
  document.addEventListener('pointerdown',function(e){ if(dlg.open && !dlg.contains(e.target) && !(e.target.closest&&e.target.closest('a.ev'))) close(); });

  var btn=document.getElementById('openAll');
  if(btn) btn.addEventListener('click',function(){
    var open=btn.getAttribute('aria-pressed')!=='true';
    document.querySelectorAll('details.deep').forEach(function(d){d.open=open;});
    btn.setAttribute('aria-pressed',open?'true':'false'); btn.textContent=btn.getAttribute(open?'data-close-label':'data-open-label');
  });
  window.addEventListener('beforeprint',function(){document.querySelectorAll('details.deep').forEach(function(d){d.open=true;});});
})();
"""
