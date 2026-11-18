#!/usr/bin/env python3
"""Fetch, search, quote and verify debate sources without loading whole pages into context.

Subcommands (run with -h for options):
  fetch  <folder> <url> [keyword ...]   download page/PDF -> cached text in evidence/files/web/, print keyword hits
                                        (--render: load it in headless Chromium first, for JavaScript sites)
  pxweb  search|meta|fetch ...          statistical tables via the PxWeb API (SiStat by default)
  sources <folder> [keyword ...]        list sources already cached in evidence/files/, matching the keywords
  search <file> <keyword ...>           keyword hits in a cached text file (also works on any local .txt/.pdf)
  show   <file> <A-B>                   print paragraphs A..B (max 40) of a cached text file
  quote  <folder> <file> <A-B> --id ... write an Evidence file whose Quote/Context are copied from the cached file
  verify <folder> [ID ...] [--live]     check each Evidence quote against its cached source and/or the live URL

Cached text files have one paragraph per line, so "line" = "paragraph" everywhere.
"""
import argparse
import datetime
import hashlib
import html
import html.parser
import json
import re
import ssl
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
MAX_BYTES = 40_000_000
SHOW_MAX_LINES = 40
SHOW_MAX_CHARS = 14_000


# ---------- download & convert ----------

def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read(MAX_BYTES), r.headers.get("Content-Type", ""), False
    except urllib.error.URLError as e:
        if "CERTIFICATE" not in str(e).upper():
            raise
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=40, context=ctx) as r:
        return r.read(MAX_BYTES), r.headers.get("Content-Type", ""), True


class _Text(html.parser.HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "iframe"}
    BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table",
             "section", "article", "blockquote", "pre", "header", "footer", "nav", "aside", "main",
             "figure", "figcaption", "dd", "dt", "hr", "form"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.title, self._in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title" and not self.title:
            self._in_title = True
        elif tag in self.BLOCK:
            self.out.append("\n")
        elif tag == "td" or tag == "th":
            self.out.append(" | ")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.out.append(data)


def _decode(raw, content_type):
    m = re.search(r"charset=([\w-]+)", content_type, re.I) or re.search(rb'charset=["\']?([\w-]+)', raw[:4000], re.I)
    tried = []
    if m:
        cs = m.group(1)
        tried.append(cs.decode() if isinstance(cs, bytes) else cs)
    for cs in tried + ["utf-8", "cp1250"]:
        try:
            return raw.decode(cs)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("latin-1")


def _paragraphs(lines):
    """Collapse whitespace, one paragraph per line, drop empties and consecutive duplicates."""
    out = []
    for ln in lines:
        ln = re.sub(r"\s+", " ", ln.replace("­", "")).strip()
        if ln and (not out or out[-1] != ln):
            out.append(ln)
    return out


def _pdf_to_paragraphs(pdf_path):
    txt = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf_path), "-"],
                         capture_output=True, text=True, check=True).stdout
    raw_lines = [ln.strip() for ln in txt.replace("\f", "\n\n").splitlines()]
    lengths = sorted(len(ln) for ln in raw_lines if len(ln) > 20)
    median = lengths[len(lengths) // 2] if lengths else 80
    paras, cur = [], []
    for ln in raw_lines:
        if re.fullmatch(r"\d{1,4}|- ?\d{1,4} ?-|\d+ ?/ ?\d+", ln):
            continue  # page numbers
        if not ln:
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        cur.append(ln)
        # A visibly short line ends a paragraph (last line of a paragraph, or a heading).
        if len(ln) < 0.8 * median:
            paras.append(" ".join(cur))
            cur = []
    if cur:
        paras.append(" ".join(cur))
    return _paragraphs(paras)


def to_paragraphs(raw, content_type, workdir):
    """Return (paragraphs, title, kind)."""
    if raw[:5] == b"%PDF-":
        p = Path(workdir) / "tmp.pdf"
        p.write_bytes(raw)
        try:
            return _pdf_to_paragraphs(p), "", "pdf"
        finally:
            p.unlink(missing_ok=True)
    text = _decode(raw, content_type)
    if "html" in content_type.lower() or re.search(r"<html|<body|<p[ >]", text[:5000], re.I):
        parser = _Text()
        parser.feed(text)
        return _paragraphs("".join(parser.out).split("\n")), html.unescape(parser.title).strip(), "html"
    return _paragraphs(text.splitlines()), "", "text"


def cache_name(url):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", re.sub(r"^https?://(www\.)?", "", url)).strip("-")[:60]
    return f"{slug}-{hashlib.sha1(url.encode()).hexdigest()[:8]}"


RENDER = Path(__file__).with_name("render.py")
DOC_LINK = re.compile(r"\.(pdf|docx?|odt|rtf)(\?|#|$)|/api/|download|prenos|objava|dokument", re.I)


def _render(url):
    """Rendered HTML via scripts/render.py (headless Chromium through `uv run --script`)."""
    r = subprocess.run(["uv", "run", "--quiet", "--script", str(RENDER), url],
                       capture_output=True, text=True, timeout=240)
    if r.returncode != 0:
        raise RuntimeError(f"render failed: {(r.stderr or r.stdout).strip()[-400:]}")
    out = json.loads(r.stdout)
    return out["html"].encode("utf-8"), "text/html; charset=utf-8", out


def fetch_to_cache(folder, url, refresh=False, render=False):
    web = Path(folder) / "evidence" / "files" / "web"
    web.mkdir(parents=True, exist_ok=True)
    base = web / (cache_name(url) + ("-rendered" if render else ""))
    txt, meta = base.with_suffix(".txt"), base.with_suffix(".json")
    if txt.exists() and not refresh:
        return txt, json.loads(meta.read_text(encoding="utf-8"))
    extra = {}
    if render:
        raw, ctype, out = _render(url)
        insecure = False
        extra = {"rendered": True, "final_url": out["url"], "status": out["status"],
                 "links": list({h: [t, h] for t, h in out["links"] if h.startswith("http")}.values())[:600]}
    else:
        raw, ctype, insecure = _get(url)
    paras, title, kind = to_paragraphs(raw, ctype, web)
    if kind == "pdf":
        base.with_suffix(".pdf").write_bytes(raw)
    txt.write_text("\n".join(paras) + "\n", encoding="utf-8")
    info = {"url": url, "fetched": datetime.date.today().isoformat(), "content_type": ctype, "kind": kind,
            "title": title, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "paragraphs": len(paras), "tls_unverified": insecure, **extra}
    meta.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return txt, info


def load_lines(path):
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        cached = path.with_suffix(".txt")
        if not cached.exists():
            cached.write_text("\n".join(_pdf_to_paragraphs(path)) + "\n", encoding="utf-8")
        path = cached
    return path, path.read_text(encoding="utf-8", errors="replace").splitlines()


# ---------- matching ----------

_TRANS = str.maketrans({"„": '"', "“": '"', "”": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "‚": "'",
                        "–": "-", "—": "-", "‑": "-", " ": " ", "­": ""})


def norm(s, fold_accents=False):
    s = unicodedata.normalize("NFKC", s).translate(_TRANS).casefold()
    if fold_accents:
        s = "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip()


def match_quality(quote, haystack_norm):
    """exact | partial | missing. Ellipses split the quote into segments checked separately."""
    segs = [norm(x) for x in re.split(r"\[\s*(?:\.\.\.|…)\s*\]|…|\.\.\.", quote)]
    segs = [s for s in segs if len(s) > 3]
    if not segs:
        return "missing"
    if all(s in haystack_norm for s in segs):
        return "exact"
    words = norm(quote).split()
    n = 6
    if len(words) < n:
        return "missing"
    shingles = [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]
    hit = sum(1 for sh in shingles if sh in haystack_norm) / len(shingles)
    return "partial" if hit >= 0.6 else "missing"


# ---------- subcommands ----------

def print_hits(lines, keywords, max_hits):
    if not keywords:
        for i, ln in enumerate(lines[:15], 1):
            print(f"L{i}: {ln[:200]}")
        return
    for kw in keywords:
        k = norm(kw, True)
        hits = [i for i, ln in enumerate(lines, 1) if k in norm(ln, True)]
        print(f"== '{kw}': {len(hits)} paragraph(s)" + (f", first {max_hits} shown" if len(hits) > max_hits else ""))
        for i in hits[:max_hits]:
            ln = lines[i - 1]
            pos = norm(ln, True).find(k)
            start = max(0, pos - 110)
            snippet = ln[start:start + 260]
            print(f"L{i}: {'…' if start else ''}{snippet}{'…' if start + 260 < len(ln) else ''}")


def cmd_fetch(a):
    try:
        txt, info = fetch_to_cache(a.folder, a.url, a.refresh, a.render)
    except Exception as e:  # noqa: BLE001 - report any failure as one line
        print(f"FAILED {a.url}: {type(e).__name__}: {e}")
        hint = "" if a.render else " If the page needs JavaScript, retry with --render."
        print(f"→{hint} If this source matters, raise an Evidence Request (paywall/blocked) or try another URL.")
        sys.exit(1)
    rel = txt.relative_to(Path(a.folder))
    flag = " (TLS certificate NOT verified)" if info.get("tls_unverified") else ""
    print(f"cached: {rel}  [{info['kind']}, {info['paragraphs']} paragraphs, fetched {info['fetched']}]{flag}")
    if info.get("title"):
        print(f"title: {info['title']}")
    lines = txt.read_text(encoding="utf-8").splitlines()
    if not a.render and info["kind"] == "html" and sum(map(len, lines)) < 1500:
        print("note: very little text; if the page needs JavaScript, retry with --render.")
    print_hits(lines, a.keywords, a.max)
    if info.get("links"):
        ks = [norm(k, True) for k in a.keywords]
        links = [l for l in info["links"]
                 if DOC_LINK.search(l[1]) or any(k in norm(l[0] + " " + l[1], True) for k in ks)]
        print(f"== document links and links matching the keywords ({len(links)}{', first 25 shown' if len(links) > 25 else ''}); fetch one to read it:")
        for text, href in links[:25]:
            print(f"  {text[:80] or '(no text)'} -> {href}")


def cmd_sources(a):
    files = Path(a.folder) / "evidence" / "files"
    ks = [norm(k, True) for k in a.keywords]
    rows = []
    for txt in sorted(files.rglob("*.txt")):
        meta = txt.with_suffix(".json")
        info = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
        label = " ".join([txt.name, info.get("title", ""), info.get("url", "")])
        body = norm(txt.read_text(encoding="utf-8", errors="replace"), True) if ks else ""
        hits = {k: body.count(k) for k in ks}
        if ks and not (any(k in norm(label, True) for k in ks) or any(hits.values())):
            continue
        rows.append((txt, info, hits))
    print(f"{len(rows)} cached source(s){' matching ' + ', '.join(a.keywords) if ks else ''}:")
    for txt, info, hits in rows:
        h = "  hits: " + ", ".join(f"{k}={n}" for k, n in hits.items()) if hits else ""
        print(f"- {txt.relative_to(Path(a.folder))}  {info.get('title', '')[:90]}  <{info.get('url', 'local file')}>{h}")


# ---------- PxWeb statistical APIs (SiStat and other PxWeb databases) ----------

PXWEB_BASE = "https://pxweb.stat.si/SiStatData/api/v1/sl/Data"


def _px_url(table, base):
    return table if table.startswith("http") else f"{base.rstrip('/')}/{table}"


def _px_json(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Content-Type": "application/json"})
    for attempt in range(4):  # PxWeb servers rate-limit (typically ~30 calls / 10 s) and reset connections
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read(MAX_BYTES), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 3:
                raise
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if attempt == 3:
                raise
        import time
        time.sleep(3 * (attempt + 1))


def _px_query(selections):
    """CODE=v1,v2 | CODE=top:N | CODE=* -> PxWeb query list."""
    q = []
    for sel in selections:
        code, _, vals = sel.partition("=")
        if not vals:
            sys.exit(f"bad selection '{sel}': use CODE=v1,v2 or CODE=top:N or CODE=*")
        if vals == "*":
            f = {"filter": "all", "values": ["*"]}
        elif vals.startswith("top:"):
            f = {"filter": "top", "values": [vals[4:]]}
        else:
            f = {"filter": "item", "values": vals.split(",")}
        q.append({"code": code, "selection": f})
    return q


def _px_rows(raw, ctype):
    """CSV -> one self-describing paragraph per row: 'COL: value | COL: value | …'."""
    import csv, io
    rows = list(csv.reader(io.StringIO(_decode(raw, ctype))))
    if not rows:
        return []
    head = rows[0]
    return [" | ".join(head)] + [" | ".join(f"{h}: {v}" for h, v in zip(head, r)) for r in rows[1:]]


def px_fetch_to_cache(folder, url, query, refresh=False):
    body = {"query": query, "response": {"format": "csv"}}
    web = Path(folder) / "evidence" / "files" / "web"
    web.mkdir(parents=True, exist_ok=True)
    base = web / (cache_name(url + json.dumps(query, sort_keys=True)) + "-pxweb")
    txt, meta = base.with_suffix(".txt"), base.with_suffix(".json")
    if txt.exists() and not refresh:
        return txt, json.loads(meta.read_text(encoding="utf-8"))
    title = json.loads(_px_json(url)[0]).get("title", "")
    raw, ctype = _px_json(url, body)
    paras = _px_rows(raw, ctype)
    txt.write_text("\n".join(paras) + "\n", encoding="utf-8")
    info = {"url": url, "fetched": datetime.date.today().isoformat(), "content_type": ctype, "kind": "pxweb",
            "title": title, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "paragraphs": len(paras), "tls_unverified": False, "post_query": body}
    meta.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    return txt, info


def cmd_pxweb(a):
    try:
        _pxweb(a)
    except urllib.error.HTTPError as e:
        print(f"FAILED: HTTP {e.code} {e.read()[:300].decode('utf-8', 'replace')}")
        print("→ Check the table id and codes with `pxweb meta`; every variable that can't be omitted needs a selection.")
        sys.exit(1)
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        print(f"FAILED: {type(e).__name__}: {e}. The server may be rate-limiting: wait a minute and retry.")
        sys.exit(1)


def _pxweb(a):
    if a.action == "search":
        q = " ".join(a.args)
        res = json.loads(_px_json(f"{a.base}?query={urllib.parse.quote(q)}")[0])
        print(f"{len(res)} table(s) for '{q}' (use a trailing * to match word stems, e.g. pokojnin*)"
              + (f", first {a.max} shown" if len(res) > a.max else ""))
        for t in res[:a.max]:
            print(f"- {t['id']}  {t['title']}  [published {t.get('published', '')[:10]}]")
    elif a.action == "meta":
        if not a.args:
            sys.exit("usage: pxweb meta <table> [CODE [keyword]]")
        d = json.loads(_px_json(_px_url(a.args[0], a.base))[0])
        if len(a.args) == 1:
            print(d.get("title", ""))
            for v in d["variables"]:
                pairs = [f"{c}={t}" for c, t in zip(v["values"], v["valueTexts"])]
                more = f" … (+{len(pairs) - 8}; list with: pxweb meta {a.args[0]} {v['code']})" if len(pairs) > 8 else ""
                tags = "".join([" [time]" if v.get("time") else "", " [can omit]" if v.get("elimination") else ""])
                print(f"{v['code']} — {v['text']}{tags}: {'; '.join(pairs[:8])}{more}")
        else:
            v = next((v for v in d["variables"] if v["code"] == a.args[1]), None)
            if not v:
                sys.exit(f"no variable {a.args[1]}")
            kw = norm(" ".join(a.args[2:]), True)
            for c, t in zip(v["values"], v["valueTexts"]):
                if kw in norm(t, True):
                    print(f"{c}={t}")
    else:  # fetch
        if not a.args:
            sys.exit("usage: pxweb fetch <table> CODE=v1,v2 … (with --folder)")
        if not a.folder:
            sys.exit("pxweb fetch needs --folder <debate folder>")
        url = _px_url(a.args[0], a.base)
        txt, info = px_fetch_to_cache(a.folder, url, _px_query(a.args[1:]), a.refresh)
        print(f"cached: {txt.relative_to(Path(a.folder))}  [pxweb, {info['paragraphs'] - 1} rows]  {info['title']}")
        lines = txt.read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(lines[:a.max + 1], 1):
            print(f"L{i}: {ln[:300]}")
        if len(lines) > a.max + 1:
            print(f"… {len(lines) - a.max - 1} more rows; read them with show, or narrow the selection.")


def cmd_search(a):
    _, lines = load_lines(a.file)
    print_hits(lines, a.keywords, a.max)


def parse_range(r, n):
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", r)
    if not m:
        sys.exit(f"bad range {r!r}; use A-B")
    s, e = int(m.group(1)), int(m.group(2) or m.group(1))
    if not (1 <= s <= e <= n):
        sys.exit(f"range {r} outside 1-{n}")
    return s, e


def cmd_show(a):
    _, lines = load_lines(a.file)
    s, e = parse_range(a.range, len(lines))
    if e - s + 1 > SHOW_MAX_LINES:
        e = s + SHOW_MAX_LINES - 1
        print(f"(capped at {SHOW_MAX_LINES} paragraphs: {s}-{e})")
    total = 0
    for i in range(s, e + 1):
        out = f"L{i}: {lines[i - 1]}"
        total += len(out)
        if total > SHOW_MAX_CHARS:
            print(f"(stopped at L{i - 1}: output cap reached; show a narrower range)")
            break
        print(out)


def _trim(text, start_at, end_after):
    if start_at:
        p = text.find(start_at)
        if p < 0:
            sys.exit(f"--from text not found in first paragraph of the range: {start_at!r}")
        text = text[p:]
    if end_after:
        p = text.rfind(end_after)
        if p < 0:
            sys.exit(f"--to text not found in last paragraph of the range: {end_after!r}")
        text = text[:p + len(end_after)]
    return text


def cmd_quote(a):
    folder = Path(a.folder)
    path, lines = load_lines(a.file)
    s, e = parse_range(a.range, len(lines))
    out = folder / "evidence" / f"{a.id}.md"
    if out.exists() and not a.force:
        sys.exit(f"{out} exists; pick the next free ID (or --force to overwrite your own file)")
    quote_paras = lines[s - 1:e]
    quote_paras[0] = _trim(quote_paras[0], a.start_at, None)
    quote_paras[-1] = _trim(quote_paras[-1], None, a.end_after)
    before = lines[max(0, s - 1 - a.context):s - 1]
    after = lines[e:e + a.context]
    meta_file = path.with_suffix(".json")
    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
    rel = str(path.relative_to(folder)) if path.is_relative_to(folder) else str(path)
    url = a.url or meta.get("url") or rel
    accessed = meta.get("fetched") or datetime.date.today().isoformat()

    def bq(paras):
        return "\n>\n".join(f"> {p}" for p in paras) if paras else "> (none: quote is at the edge of the source)"

    parts = [
        "---",
        f"id: {a.id}",
        f"added_by: {a.added_by}",
        f"stage: {a.stage}",
        f"url: {url}",
        f"accessed: {accessed}",
        f"title: {a.title}",
        f"author: {a.author}",
        f"publisher: {a.publisher}",
        f"published: {a.published}",
        f"language: {a.language}",
        f"source_file: {rel}",
        f"source_lines: {s}-{e}",
        "---",
        "",
        "## Quote",
        "",
        bq(quote_paras),
        "",
    ]
    if a.translation:
        parts += ["## Translation", "", f"> {a.translation}", ""]
    parts += [
        "## Context",
        "",
        "Before:",
        "",
        bq(before),
        "",
        "After:",
        "",
        bq(after),
        "",
        "## Audit",
        "",
        "- Quote found:",
        "- Supports:",
        "- Cherry-picked:",
        "- Source Tier:",
        "- Funder/affiliation:",
        "- Notes:",
        "",
    ]
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote evidence/{a.id}.md ({len(' '.join(quote_paras))} chars quoted from {rel} L{s}-{e})")


def _section(text, name):
    m = re.search(rf"^## {name}\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        return ""
    return " ".join(ln.lstrip(">").strip() for ln in m.group(1).splitlines() if ln.startswith(">"))


def _front(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    out = {}
    for ln in (m.group(1).splitlines() if m else []):
        if ":" in ln:
            k, v = ln.split(":", 1)
            out[k.strip()] = re.sub(r"\s+#\s.*$", "", v).strip()
    return out


def cmd_verify(a):
    folder = Path(a.folder)
    files = sorted((folder / "evidence").glob("E-*.md"))
    if a.ids:
        want = set(a.ids)
        files = [f for f in files if f.stem in want]
    print("| Evidence | cached copy | live source | note |\n|---|---|---|---|")
    for f in files:
        text = f.read_text(encoding="utf-8")
        fm, quote = _front(text), _section(text, "Quote")
        if not quote:
            print(f"| {f.stem} | no quote | — | Quote section empty |")
            continue
        url, note = fm.get("url", ""), []
        cached = "—"
        src = fm.get("source_file")
        local = src or (url if url and not url.startswith("http") else "")
        if local:
            p = folder / local
            if p.exists():
                _, lines = load_lines(p)
                cached = match_quality(quote, norm(" ".join(lines)))
            else:
                cached = "file missing"
        live = "—"
        if url.startswith("http") and (a.live or not local):
            try:
                rendered = bool(src) and src.endswith("-rendered.txt")
                with tempfile.TemporaryDirectory() as td:
                    pmeta = (folder / src).with_suffix(".json") if src else None
                    pq = json.loads(pmeta.read_text(encoding="utf-8")).get("post_query") if pmeta and pmeta.exists() else None
                    insecure = False
                    if pq:
                        raw, ctype = _px_json(url, pq)
                        paras = _px_rows(raw, ctype)
                        note.append("re-queried")
                    elif rendered:
                        (raw, ctype, _), insecure = _render(url), False
                        note.append("re-rendered")
                    else:
                        raw, ctype, insecure = _get(url)
                    if not pq:
                        paras, _, _ = to_paragraphs(raw, ctype, td)
                live = match_quality(quote, norm(" ".join(paras)))
                if insecure:
                    note.append("TLS unverified")
            except Exception as e:  # noqa: BLE001
                live = "unreachable"
                note.append(f"{type(e).__name__}: {str(e)[:60]}")
        print(f"| {f.stem} | {cached} | {live} | {'; '.join(note)} |")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("fetch", help="download a URL into the debate's cache and search it")
    p.add_argument("folder")
    p.add_argument("url")
    p.add_argument("keywords", nargs="*")
    p.add_argument("--refresh", action="store_true", help="re-download even if cached")
    p.add_argument("--max", type=int, default=8, help="max hits per keyword (default 8)")
    p.add_argument("--render", action="store_true", help="load the page in headless Chromium (JavaScript sites)")
    p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser("sources", help="list sources already cached in evidence/files/")
    p.add_argument("folder")
    p.add_argument("keywords", nargs="*")
    p.set_defaults(fn=cmd_sources)

    p = sub.add_parser("pxweb", help="statistical tables via the PxWeb API (SiStat by default)")
    p.add_argument("action", choices=["search", "meta", "fetch"])
    p.add_argument("args", nargs="*", help="search: words | meta: table [CODE [keyword]] | fetch: table CODE=v1,v2 …")
    p.add_argument("--folder", help="debate folder (fetch only)")
    p.add_argument("--base", default=PXWEB_BASE, help=f"PxWeb API base (default {PXWEB_BASE})")
    p.add_argument("--max", type=int, default=20, help="tables or rows to print (default 20)")
    p.add_argument("--refresh", action="store_true")
    p.set_defaults(fn=cmd_pxweb)

    p = sub.add_parser("search", help="keyword hits in a cached/local file")
    p.add_argument("file")
    p.add_argument("keywords", nargs="+")
    p.add_argument("--max", type=int, default=8)
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("show", help="print paragraphs A-B of a cached/local file")
    p.add_argument("file")
    p.add_argument("range")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("quote", help="write an Evidence file quoting paragraphs A-B verbatim")
    p.add_argument("folder")
    p.add_argument("file", help="cached .txt (or local .pdf/.txt) the quote comes from")
    p.add_argument("range", help="paragraph range A-B of the quote")
    p.add_argument("--id", required=True)
    p.add_argument("--added-by", required=True)
    p.add_argument("--stage", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--author", default="unknown")
    p.add_argument("--publisher", required=True)
    p.add_argument("--published", default="unknown")
    p.add_argument("--language", required=True)
    p.add_argument("--from", dest="start_at", help="start the quote at this exact text within paragraph A")
    p.add_argument("--to", dest="end_after", help="end the quote after this exact text within paragraph B")
    p.add_argument("--context", type=int, default=1, help="paragraphs of context before and after (default 1)")
    p.add_argument("--translation", help="translation of the quote into the Report language")
    p.add_argument("--url", help="override the source URL (default: from the cache metadata)")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_quote)

    p = sub.add_parser("verify", help="check Evidence quotes against cached and/or live sources")
    p.add_argument("folder")
    p.add_argument("ids", nargs="*")
    p.add_argument("--live", action="store_true", help="also re-download every http source")
    p.set_defaults(fn=cmd_verify)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
