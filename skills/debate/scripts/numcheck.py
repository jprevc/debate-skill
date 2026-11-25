"""Numbers in prose, read the way an English or Slovenian writer means them, and matched against the numbers
in the Evidence a sentence cites. Used by report_html.py and short_html.py (the NUMBER check of the Report's
prose and of the figure values in figures.json) and by evidence.py calc.

A number in the Report matches a number in an Evidence file when they are the same quantity once the scale
word ("million", "mio", "milijard" …) is applied, and the Evidence's number rounds to the Report's number at
the Report's precision: "EUR 80 million" matches "79,6 mio EUR", "EUR 1.2 billion" matches "1.195 mio EUR",
and "80" does not match "75". Signs are ignored, because a table's "−53" is the Report's "a loss of 53".
"""
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

PCT_AFTER = re.compile(r"(?:%|odstot|percent|per cent)", re.I)
# scale words after a number, matched at a word start
SCALES = [
    (re.compile(r"(?:thousands?|k\b|tisoč\w*|tis\.)", re.I), Decimal(10) ** 3),
    (re.compile(r"(?:millions?|mn\b|mio\b|mil\.|m\b|milijon\w*)", re.I), Decimal(10) ** 6),
    (re.compile(r"(?:billions?|bn\b|milijard\w*|mrd\b\.?)", re.I), Decimal(10) ** 9),
]
SPACES = "   "
# a number: digits with optional thousands groups and decimals, in either convention
NUM_RE = re.compile(rf"(?<![\w.,])(?P<num>\d{{1,3}}(?:[.,{SPACES}]\d{{3}})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)(?!\w)")
# what makes a number a reference rather than a quantity: an article, paragraph, point, page, table or line
REF_BEFORE = re.compile(
    r"(?:\b(?:Arts?|Articles?|členi?|člena|členov|členu|odst|odstavek|točk\w*|tč|para|paras|paragraphs?|"
    r"p|pp|pages?|str|strani|lines?|vrstic\w*|no|nr|Table|Tabela|Figure|Slika|Graf|Chart|Section|poglavje|"
    r"batch)\.?|§|No\.|št\.)\s*(?:\d+[a-z]?\s*(?:[,–\-]|and|in|to|do)\s*)*$", re.I)
ID_NEAR = re.compile(r"\b(?:E|R|PRO|CON)-[A-Z0-9-]*$")
MONTHS = (r"January|February|March|April|May|June|July|August|September|October|November|December|"
          r"januar\w*|februar\w*|mar[cč]\w*|april\w*|maj\w*|junij\w*|julij\w*|avgust\w*|septemb\w*|oktob\w*|novemb\w*|decemb\w*")
DATE_RE = re.compile(rf"\b\d{{1,2}}\.\s?\d{{1,2}}\.\s?\d{{4}}\b|\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}}\.?\s+(?:{MONTHS})\b", re.I)
EVID = r"E-(?:PRIMARY|USER|PRO|CON)(?:-[A-Z])?-\d{3}"
LINK_RE = re.compile(rf"\[({EVID})\]\([^)]*\)|\b({EVID})\b")


class Num:
    """One number as written, with every (value, decimals) it can mean ("1,200" is 1200 or 1.2), the scale
    word after it, and whether a percent sign or word follows it."""
    __slots__ = ("text", "start", "values", "scale", "pct")

    def __init__(self, text, start, values, scale, pct=False):
        self.text, self.start, self.values, self.scale, self.pct = text, start, values, scale, pct

    def __repr__(self):
        return f"Num({self.text!r}, {sorted(str(v) for v, _ in self.values)}, scale={self.scale})"


def readings(s):
    """Every (value, decimals) a written number can mean, in the English and the Slovenian convention."""
    s = re.sub(f"[{SPACES}]", "", s)
    if not re.search(r"[.,]", s):
        return {(Decimal(s), 0)}
    out = set()
    for thou, dec in ((",", "."), (".", ",")):
        groups = s.split(dec)
        if len(groups) > 2:
            continue
        whole, frac = groups[0], (groups[1] if len(groups) == 2 else "")
        if thou in frac:
            continue
        parts = whole.split(thou)
        if len(parts) > 1 and (not 1 <= len(parts[0]) <= 3 or any(len(p) != 3 for p in parts[1:])):
            continue
        try:
            out.add((Decimal("".join(parts) + ("." + frac if frac else "")), len(frac)))
        except InvalidOperation:
            continue
    return out


def _is_reference(masked, m):
    """A number that names something rather than measuring it: an article, page or case number, an ID, a year,
    a Slovenian ordinal or a vote count."""
    before, after = masked[max(0, m.start() - 40):m.start()], masked[m.end():m.end() + 12]
    if REF_BEFORE.search(before) or ID_NEAR.search(before):
        return True
    if re.fullmatch(r"(?:19|20)\d\d", m["num"]) and not re.match(r"\s?%", after):
        return True  # a year
    if re.match(r"\.(?:\s+[a-zčšž]|,)", after):
        return True  # an ordinal: "25. in 26. člen", "29. decembra", "21., 24. in 56. členu"
    # a case or file number (U-I-79/25), a vote (6:3), a span of years (2024-25), an ID tail
    return bool(re.search(r"(?:[A-Za-z]-|\d/|\d:|(?:19|20)\d\d[-–/])$", before) or re.match(r"[/:]\d", after))


def numbers(text, quantities_only=True):
    """The numbers in a text. With quantities_only (for prose that cites Evidence), dates, years, IDs and
    article, page or case numbers are left out; an Evidence file keeps every number, so any of them can match."""
    masked = DATE_RE.sub(lambda m: " " * len(m.group(0)), text) if quantities_only else text
    found = []
    for m in NUM_RE.finditer(masked):
        if quantities_only and _is_reference(masked, m):
            continue
        vals = readings(m["num"])
        if not vals:
            continue
        # the scale word after the number, or after the end of its range ("EUR 234-257 million")
        rest = re.sub(r"^\s*[-–]\s*\d[\d.,]*", "", masked[m.end():m.end() + 30]).lstrip()
        scale = next((mult for rx, mult in SCALES if rx.match(rest)), Decimal(1))
        found.append(Num(m["num"], m.start(), vals, scale, bool(PCT_AFTER.match(rest))))
    return found


def _round(q, d):
    return q.quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP)


def matches(n, pool):
    """Whether Num n is one of the Nums in pool: the same quantity, the pool's number rounded to n's precision.
    A pool number without a scale word is also read at n's scale (a table headed "mio EUR")."""
    for v, d in n.values:
        for p in pool:
            for ps in ({p.scale, n.scale} if p.scale == 1 else {p.scale}):
                for pv, _ in p.values:
                    try:
                        if _round(abs(pv) * ps / n.scale, d) == v:
                            return True
                    except InvalidOperation:
                        continue
    return False


def section(text, name):
    """The blockquoted lines of a "## <name>" section of an Evidence file, joined."""
    m = re.search(rf"^## {name}\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return " ".join(ln.lstrip(">").strip() for ln in m.group(1).splitlines() if ln.startswith(">")) if m else ""


def evidence_numbers(text, translation=True):
    """Every number in an Evidence file's Quote and Context (both verbatim from the source), and its Translation."""
    names = ("Quote", "Context") + (("Translation",) if translation else ())
    return [n for name in names for n in numbers(section(text, name), quantities_only=False)]


# A figure in a percent unit may give 37 for the Evidence's fraction 0.37, and one in a share unit 0.37 for its
# 37 %. Other units get no such factor: a scale word converts exactly ("17,9 tisoč" is 17900), and a bare factor
# of 100 or 1000 would let a figure's 6400 or 48000 pass on any "64" or "48" in the Evidence.
PERCENT_UNIT = re.compile(r"%|\bper ?cent|\bodstot", re.I)
SHARE_UNIT = re.compile(r"\b(?:share|rate|ratio|fraction|delež\w*|stopnj\w*)\b", re.I)


def unit_scale(unit):
    """The scale word in a figure's unit ("EUR million" → 10**6), or 1."""
    for m in re.finditer(r"\b(?=\w)", unit or ""):
        for rx, mult in SCALES:
            if rx.match(unit, m.start()):
                return mult
    return Decimal(1)


def value_matches(v, unit, pool):
    """Whether a figure value (a JSON number in the figure's unit, such as "EUR million") is one of the Nums in
    pool, rounded to the value's precision (80.0 is read as 80); a percentage may be a fraction in the Evidence,
    and a share a percentage (see PERCENT_UNIT)."""
    d = Decimal(repr(v)).normalize()
    num = lambda k: Num(str(v), 0, {(abs(d), max(0, -d.as_tuple().exponent))}, unit_scale(unit) * k)  # noqa: E731
    if matches(num(1), pool):
        return True
    if PERCENT_UNIT.search(unit or ""):
        fractions = [p for p in pool if not p.pct and all(abs(pv) <= 10 for pv, _ in p.values)]
        return matches(num(Decimal("0.01")), fractions)
    if SHARE_UNIT.search(unit or ""):
        return matches(num(Decimal(100)), [p for p in pool if p.pct])
    return False


SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZČŠŽ(\"“„»*])")


def check_prose(text, name, evdir):
    """NUMBER problems: in each sentence (or table row) that cites Evidence, the numbers that none of the cited
    Evidence files states. A sentence that cites nothing is not checked; nor is a fenced or HTML block."""
    pools, problems = {}, []

    def pool(eid):
        if eid not in pools:
            p = Path(evdir) / f"{eid}.md"
            pools[eid] = evidence_numbers(p.read_text(encoding="utf-8")) if p.exists() else None
        return pools[eid]

    fence = False
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
        if fence or line.lstrip().startswith("<"):
            continue
        for sent in [line] if line.lstrip().startswith("|") else SENTENCE_RE.split(line):
            ids = list(dict.fromkeys(a or b for a, b in LINK_RE.findall(sent)))
            known = [p for e in ids if (p := pool(e)) is not None]
            if not known:
                continue  # cites nothing, or only missing files (reported elsewhere)
            prose = re.sub(r"\]\([^)]*\)", "]", LINK_RE.sub(" ", sent))
            flat = [n for p in known for n in p]
            bad = list(dict.fromkeys(n.text for n in numbers(prose) if not matches(n, flat)))
            if bad:
                problems.append(f"NUMBER {name}:{i}: {', '.join(bad)} {'is' if len(bad) == 1 else 'are'} in none of "
                                f"{', '.join(ids)}")
    return problems
