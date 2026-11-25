"""A Slovenian bill's amending articles applied to the consolidated law they amend (PIS), article by article.
Used by evidence.py lawdiff, which caches each amended article before and after.

Amending acts phrase their changes in a few set ways ("se spremeni tako, da se glasi", "se črta", "za … se doda",
"se nadomesti z"). apply_amendment reads those and raises Unparsed on anything else, or on a change it can't place
exactly, so that the caller shows the article in force and the amending article as both full texts instead.
"""
import re
import unicodedata

ARTICLE_NUM = r"\d+\.[a-zčšž]?"  # "2.", "3.a"
ARTICLE_HEAD = re.compile(rf"^({ARTICLE_NUM}) člen$")
LAW_NOISE = re.compile(r"^(Sodna praksa|Opomba:|3\d{4}[A-Z]\d{4}$)")
AMENDING_ACT = re.compile(r"^\d{4}-\d{2}-\d+\S*Zakon")  # PIS lists the amending acts' own provisions after the law
# the act's citation that opens the first amending article: "V Zakonu o … (Uradni list RS, št. …) "
ACT_CITATION = re.compile(r"^V Zakonu o [^(]*\((?:[^()]|\([^()]*\))*\) ")
# an act's abbreviation in brackets: "(ZDoh-2)", "(ZIURS)"
ABBREVIATION = re.compile(r"\(([A-ZČŠŽ]{2,}[A-Za-zČŠŽčšž]*(?:-\d+[A-Za-z]*)?)\)")

ORDINALS = ["prv", "drug", "tretj", "četrt", "pet", "šest", "sedm", "osm", "devet", "deset", "enajst", "dvanajst",
            "trinajst", "štirinajst", "petnajst", "šestnajst", "sedemnajst", "osemnajst", "devetnajst", "dvajset"]
# an ordinal number word in any case and gender: "tretji", "drugem", "četrtega"
ORDINAL = rf"(?:{'|'.join(sorted(ORDINALS, key=len, reverse=True))})(?:i|em|ega|im|a|e|o|ih|ima)?\b"
ORDINAL_LIST = rf"{ORDINAL}(?:(?:, | in | do ){ORDINAL})*"  # "tretji, četrti in peti", "osmi do enajsti"
# the noun before a quoted text that is struck out or replaced: "besedilo »…«", "stopnja »…«"
QUOTED_NOUN = r"(?:besedilo|beseda|besedi|besede|stopnja|število|znesek|kratica|letnica|datum)"
# the same nouns after "z"/"s", before the replacement text: "z besedilom »…«", "s stopnjo »…«"
QUOTED_NOUN_WITH = r"(?:besedilom|besedo|besedama|besedami|stopnjo|številom|zneskom|kratico|letnico|datumom)"
NUMBERED = re.compile(r"^\((\d+)\) ")


class Unparsed(Exception):
    """An amending article lawdiff can't apply; it is shown as both full texts."""


def _art(num):
    return num if "." in num else num + "."


def one_line(s):
    return re.sub(r"\s+", " ", s).strip()


def strip_act_citation(body):
    """An amending article's text on one line, without the act's citation that opens the first one."""
    return ACT_CITATION.sub("", one_line(body))


def law_articles(lines):
    """{'2.': {'num', 'title', 'paras'}} from a PIS consolidated text: each article's first appearance, up to the
    amending acts' provisions. A paragraph starts with (n); bullets and table rows join the paragraph above."""
    arts, cur = {}, None
    for ln in lines:
        if AMENDING_ACT.match(ln):
            break
        m = ARTICLE_HEAD.match(ln)
        if m:
            cur = None if m[1] in arts else arts.setdefault(m[1], {"num": m[1], "title": "", "paras": []})
            continue
        if cur is None or LAW_NOISE.match(ln):
            continue
        if re.match(r"^[IVXLC]+\.( |$)|.*\bpoglavje:", ln):
            continue  # a chapter heading between articles
        if ln.startswith("(") and not re.match(r"^\(\d+\) ", ln) and not cur["title"] and not cur["paras"]:
            cur["title"] = ln
        elif re.match(r"^\(\d+\) ", ln) or not cur["paras"]:
            cur["paras"].append(ln)
        else:
            cur["paras"][-1] += " " + ln
    return arts


def bill_articles(lines):
    """[(num, body)] of a bill: an article heading stands alone at the end of a paragraph, outside quotation marks
    (a PDF extract may run it on after the previous paragraph's text)."""
    text = "\n".join(lines)
    heads = []
    for m in re.finditer(rf"(?:(?<=\n)|(?<=^)|(?<=[.:«] )|(?<=[A-ZČŠŽ] ))({ARTICLE_NUM}) člen(?=\n|$)", text):
        before = text[:m.start()]
        if before.count("»") <= before.count("«"):
            heads.append(m)
    bodies = [text[m.end():(heads[k + 1].start() if k + 1 < len(heads) else len(text))] for k, m in enumerate(heads)]
    # a part or section heading ("TRETJI DEL", "2. ZAKON O DAVKIH") closes the body of the article before it
    tail = re.compile(r"(?:\s+(?:\d+\.\s+)?[A-ZČŠŽ]{2,}(?:[ ,]+[A-ZČŠŽ]{1,}\.?)+)+\s*$")
    return [(m[1], tail.sub("", b).strip()) for m, b in zip(heads, bodies)]


def act_name(s):
    """'Zakon o dohodnini (ZDoh-2) (PISRS)' and 'V Zakonu o dohodnini (Uradni list …' -> 'o dohodnini'."""
    s = one_line(unicodedata.normalize("NFKC", s).replace("­", "").casefold())
    m = re.search(r"\bzakon\w* (o .*?)\s*(?:\(|$)", s, re.I)
    return m[1] if m else ""


def act_section(articles, name, wanted=None):
    """The bill's amending articles on the act called `name`: from the article that cites it ("V Zakonu o …
    (Uradni list …)") up to the next act's first article or the first article with a title (a provision of the
    bill's own, not an amendment). With `wanted` ("15,16,17"), exactly those articles."""
    if wanted:
        keep = {_art(w.strip()) for w in wanted.split(",") if w.strip()}
        return [(n, b) for n, b in articles if n in keep]
    out = []
    for n, b in articles:
        cites = re.match(r"^V Zakonu o ", b)
        if out and (cites or b.startswith("(")):
            break
        if out or (cites and act_name(b.split(")", 1)[0]) == name):
            out.append((n, b))
    return out


def abbreviation(title, lines):
    """The act's abbreviation, from its title or else from the first lines of its text; '' if neither has one."""
    m = ABBREVIATION.search(title or "") or next((m for ln in lines[:30] if (m := ABBREVIATION.search(ln))), None)
    return m[1] if m else ""


def amended_article(body):
    """The law article an amending article amends, for showing it when it can't be applied: the one its
    'V N. členu' names, else the first article it mentions; '?' if none."""
    text, _ = quoted(strip_act_citation(body))
    ref = re.search(rf"\bv ({ARTICLE_NUM}) členu\b", text, re.I) or re.search(rf"({ARTICLE_NUM}) člen", text)
    return ref[1] if ref else "?"


def quoted(body):
    """The body with each top-level »…« replaced by ⟦i⟧, and the quoted texts."""
    out, quotes, depth, buf = "", [], 0, ""
    for ch in body:
        if ch == "»":
            if depth:
                buf += ch
            depth += 1
        elif ch == "«" and depth:
            depth -= 1
            if depth:
                buf += ch
            else:
                out += f"⟦{len(quotes)}⟧"
                quotes.append(buf)
                buf = ""
        elif depth:
            buf += ch
        else:
            out += ch
    return out, quotes


def _numbered(text):
    """Split a new text into its paragraphs (1), (2) … : a marker counts only in sequence, so a reference to
    'točka (12)' inside a sentence doesn't start a paragraph."""
    text, starts, n, pos = one_line(text), [], 1, 0
    while (m := re.compile(rf"(?:^|(?<= ))\({n}\) ").search(text, pos)):
        starts.append(m.start())
        pos, n = m.end(), n + 1
    if not starts:
        return [text] if text else []
    head = [text[:starts[0]].strip()] if starts[0] else []
    return head + [text[a:b].strip() for a, b in zip(starts, starts[1:] + [len(text)])]


def _new_article(text):
    """(title, paragraphs) of an article quoted in the bill."""
    text = one_line(text)
    m = re.match(rf"^{ARTICLE_NUM} člen (\([^()]*\) )?", text)
    if m:
        return (m[1] or "").strip(), _numbered(text[m.end():])
    return "", _numbered(text)


def render_article(num, title, paras):
    return " ".join(x for x in [f"{num} člen", title, *paras] if x)


def _ordinal(word):
    word = word.lower()
    return next(i + 1 for i, s in sorted(enumerate(ORDINALS), key=lambda x: -len(x[1])) if word.startswith(s))


def _ordinals(text):
    """'Tretji, četrti in peti' -> [3, 4, 5]; 'osmi do enajsti' -> [8, …, 11]."""
    ns = [_ordinal(w) for w in re.findall(ORDINAL, text, re.I)]
    return list(range(ns[0], ns[1] + 1)) if " do " in text and len(ns) == 2 else ns


def _nth(n):
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10 if n not in (11, 12, 13) else 0, 'th')}"


class _Article:
    """An article being amended: its title and paragraphs, each remembering its number in the law in force, as the
    bill names paragraphs by the numbers they had before the change ("dosedanji sedmi odstavek")."""

    def __init__(self, art):
        self.title, self.paras = art["title"], []
        for p in art["paras"]:
            m = NUMBERED.match(p)
            self.paras.append({"old": int(m[1]) if m else None, "numbered": bool(m), "text": p[m.end():] if m else p})

    def index(self, n):
        i = next((i for i, p in enumerate(self.paras) if p["old"] == n), None)
        if i is None:
            raise Unparsed(f"no {_nth(n)} paragraph in the consolidated text")
        return i

    def new_number(self, n):
        """The number the old n-th paragraph has now, or None if it was struck out."""
        k = 0
        for p in self.paras:
            k += p["numbered"]
            if p["old"] == n:
                return k
        return None

    def rendered(self):
        out, k = [], 0
        for p in self.paras:
            k += p["numbered"]
            out.append(f"({k}) {p['text']}" if p["numbered"] else p["text"])
        return self.title, out


def _replace_text(text, old, new, where):
    old = one_line(old)
    n = text.count(old)
    if n == 0:
        raise Unparsed(f"»{old}« is not in the {where}")
    if n > 1:
        raise Unparsed(f"»{old}« stands {n} times in the {where}")
    text = text.replace(old, one_line(new), 1)
    return re.sub(r" +([,.;:])", r"\1", re.sub(r"  +", " ", text)).strip()


def _new_paras(text):
    return [{"old": None, "numbered": bool(NUMBERED.match(p)), "text": NUMBERED.sub("", p)} for p in _numbered(text)]


def apply_amendment(body, law):
    """{law article: (before, after)} for one amending article; before/after are (title, paragraphs) or None.
    `law` is law_articles() of the consolidated text. Raises Unparsed on a phrasing it doesn't read, or on a change
    it can't place exactly."""
    text, quotes = quoted(strip_act_citation(body))
    sentences = [s.strip() for s in re.split(r"(?<=[.⟧])\s+(?=[A-ZČŠŽ0-9])", text) if s.strip()]
    changes = {}
    edited = {}  # law article -> _Article being edited by "V N. členu …" sentences
    renumberings = {}  # law article -> [(old paragraph number, the new number the bill gives it)]
    target = None  # the law article the current sentence edits: the last one a "V N. členu" named

    def article(num):
        if num not in law:
            raise Unparsed(f"{num} člen is not in the consolidated text")
        return law[num]

    def quote(i):
        return quotes[int(i)]

    for s in sentences:
        s = s.rstrip(".").strip()
        if re.fullmatch(r"\d+", s) or s == s.upper():
            continue  # a section heading run into the article's last paragraph
        m = re.match(rf"^(?:se )?({ARTICLE_NUM}) člen (?:se )?spremeni tako, da se glasi:? ⟦(\d+)⟧$", s, re.I)
        if m:
            a = article(m[1])
            changes[m[1]] = ((a["title"], a["paras"]), _new_article(quote(m[2])))
            continue
        m = re.match(rf"^(?:se )?({ARTICLE_NUM}) člen (?:se )?črta$", s, re.I)
        if m:
            a = article(m[1])
            changes[m[1]] = ((a["title"], a["paras"]), None)
            continue
        m = re.match(rf"^(?:se )?za ({ARTICLE_NUM}) členom (?:se )?doda nov ({ARTICLE_NUM}) člen, ki se glasi:? ⟦(\d+)⟧$",
                     s, re.I)
        if m:
            changes[m[2]] = (None, _new_article(quote(m[3])))
            continue
        # an instruction inside an article: first where (article, paragraph, title), then what
        m = re.match(rf"^(?:se )?v ({ARTICLE_NUM}) členu,? ", s, re.I)
        if m:
            target, s = m[1], s[m.end():]
        if target is None:
            raise Unparsed(f"phrasing not handled: {s[:100]}")
        if target not in edited:
            edited[target] = _Article(article(target))
        art, scope = edited[target], None
        m = re.match(rf"^(?:se )?v (?:dosedanj\w+ )?({ORDINAL}) odstavku(?:, ki postane ({ORDINAL}) odstavek,)? ", s, re.I)
        if m:
            scope, s = art.index(_ordinal(m[1])), s[m.end():]
            if m[2]:
                renumberings.setdefault(target, []).append((_ordinal(m[1]), _ordinal(m[2])))
        elif m := re.match(r"^(?:se )?v besedilu člena, ki se označi kot prvi odstavek,? ", s, re.I):
            if len(art.paras) != 1 or art.paras[0]["numbered"]:
                raise Unparsed("the article is not one unnumbered paragraph")
            art.paras[0].update(numbered=True, old=1)
            scope, s = 0, s[m.end():]
        elif m := re.match(r"^(?:se )?v naslovu člena ", s, re.I):
            scope, s = "title", s[m.end():]
        s = re.sub(r"^se ", "", s)

        def edit(old, new):
            if scope == "title":
                art.title = "(" + _replace_text(art.title.strip("()"), old, new, "title") + ")"
                return
            i = scope
            if i is None:
                if len(art.paras) != 1:
                    raise Unparsed(f"no paragraph named for »{one_line(old)}«")
                i = 0
            where = f"{_nth(art.paras[i]['old'])} paragraph" if art.paras[i]["old"] else "article"
            art.paras[i]["text"] = _replace_text(art.paras[i]["text"], old, new, where)

        m = re.match(rf"^(?:črta(?:ta|jo)? {QUOTED_NOUN} ⟦(\d+)⟧|{QUOTED_NOUN} ⟦(\d+)⟧ (?:se )?črta(?:ta|jo)?)$", s, re.I)
        if m:
            edit(quote(m[1] or m[2]), "")
            continue
        m = re.match(rf"^{QUOTED_NOUN} ⟦(\d+)⟧ (?:se )?nadomesti(?:ta|jo)? (?:z|s) {QUOTED_NOUN_WITH} ⟦(\d+)⟧$", s, re.I)
        if m:
            edit(quote(m[1]), quote(m[2]))
            continue
        if scope is not None:
            raise Unparsed(f"phrasing not handled: {s[:100]}")
        m = re.match(rf"^({ORDINAL_LIST}) odstav\w+ (?:se )?črta(?:ta|jo)?$", s, re.I)
        if m:
            gone = {art.index(n) for n in _ordinals(m[1])}
            art.paras = [p for i, p in enumerate(art.paras) if i not in gone]
            continue
        m = re.match(rf"^({ORDINAL}) odstavek (?:se )?spremeni tako, da se glasi:? ⟦(\d+)⟧$", s, re.I)
        if m:
            i, new = art.index(_ordinal(m[1])), _new_paras(quote(m[2]))
            if len(new) != 1:
                raise Unparsed("one paragraph replaced by several")
            art.paras[i]["text"] = new[0]["text"]
            continue
        m = re.match(rf"^za ({ORDINAL}) odstavkom (?:se )?doda(?:ta|jo)? nov\w* ({ORDINAL_LIST}) odstav\w+, ki se "
                     rf"glas\w+:? ⟦(\d+)⟧$", s, re.I)
        if m:
            i = art.index(_ordinal(m[1]))
            art.paras[i + 1:i + 1] = _new_paras(quote(m[3]))
            continue
        m = re.match(rf"^dosedanj\w+ ({ORDINAL_LIST}) odstav\w+ postane(?:ta|jo)? ({ORDINAL_LIST}) odstav\w+$", s, re.I)
        if m:
            olds, news = _ordinals(m[1]), _ordinals(m[2])
            if len(olds) != len(news):
                raise Unparsed(f"can't read the renumbering: {s[:80]}")
            renumberings.setdefault(target, []).extend(zip(olds, news))
            continue
        raise Unparsed(f"phrasing not handled: {s[:100]}")
    for num, art in edited.items():
        for old, new in renumberings.get(num, []):  # the bill states the new numbers: they must agree with the edits
            got = art.new_number(old)
            if got != new:
                raise Unparsed(f"the bill makes the old {_nth(old)} paragraph the {_nth(new)}, lawdiff "
                               f"{'the ' + _nth(got) if got else 'struck it out'}")
        a = law[num]
        changes[num] = ((a["title"], a["paras"]), art.rendered())
    return changes
