#!/usr/bin/env python3
"""Fetch, search, quote and verify debate sources without loading whole pages into context.

Subcommands (run with -h for options):
  fetch  <folder> <url> [keyword ...]   download page/PDF -> cached text in evidence/files/web/, print keyword hits
                                        (--render: load it in headless Chromium first, for JavaScript sites;
                                         --archive: the latest Wayback Machine snapshot, for a site that is down)
  pxweb  search|meta|fetch ...          statistical tables via the PxWeb API (SiStat by default)
  papers <words ...> | <DOI>            research papers via OpenAlex: search, or one paper's type, retraction,
                                        funders and open copies (OPENALEX_API_KEY optional)
  data   <folder> <script.py>           run a pinned statistics script (sistat, wbgapi, sdmx1 …) with uv and
                                        cache its rows as text in evidence/files/data/; verify --live re-runs it
  import <folder> <file> --name <slug>  text of a file the user supplied (in sources/) -> evidence/files/user-<slug>.txt;
                                        the original is never changed, and its path becomes the Evidence url
  sources <folder> [keyword ...]        list sources already cached in evidence/files/, matching the keywords
  search <file> <keyword ...>           keyword hits in a cached text file (also works on any local .txt/.pdf)
  show   <file> <A-B>                   print paragraphs A..B (max 40) of a cached text file
  quote  <folder> <file> <A-B> --id ... write an Evidence file whose Quote/Context are copied from the cached file
                                        (with EVIDENCE_ARCHIVE=1, a web page is snapshot by Save Page Now: archive_url)
  archive <folder>                      snapshot the quoted web pages that have no archive_url yet (EVIDENCE_ARCHIVE=1)
  calc   <folder> "<formula>" --id ...  write an Evidence file that computes a number from numbers in other Evidence,
                                        e.g. "E-CON-001:1195 / E-PRO-004:63900 * 100"; verify recomputes it
  verify <folder> [ID ...] [--live]     check each Evidence quote against its cached source and/or the live URL,
                                        and recompute each calc
                                        (live: exact | partial | missing | unreachable, or unchanged when the
                                        download is byte-identical to the cached one; when a web page is down,
                                        archived <date>: exact | partial | missing against its snapshot)

Cached text files have one paragraph per line, so "line" = "paragraph" everywhere.
<folder> is the debate's agent/ folder; a project folder that contains agent/ is accepted too.
"""
import argparse
import ast
import datetime
import decimal
import hashlib
import html
import html.parser
import json
import operator
import os
import re
import ssl
import subprocess
import sys
import tempfile
import time
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


def fetch_to_cache(folder, url, refresh=False, render=False, archive=False):
    if render and archive:
        raise ValueError("--render and --archive don't combine: the archive keeps what the site served")
    web = Path(folder) / "evidence" / "files" / "web"
    web.mkdir(parents=True, exist_ok=True)
    base = web / (cache_name(url) + ("-rendered" if render else "-archived" if archive else ""))
    txt, meta = base.with_suffix(".txt"), base.with_suffix(".json")
    if txt.exists() and not refresh:
        return txt, json.loads(meta.read_text(encoding="utf-8"))
    extra = {}
    if archive:
        snapshot = _latest_snapshot(url)
        if not snapshot:
            raise LookupError("the Wayback Machine has no snapshot of this URL")
        raw, ctype, insecure = _get_snapshot(snapshot)
        extra = {"archive_url": snapshot, "archived": _snapshot_date(snapshot)}
    elif render:
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


# ---------- the Wayback Machine (archive.org) ----------

WAYBACK_API = "https://archive.org/wayback/available?url="
SNAPSHOT_RE = re.compile(r"^https?://web\.archive\.org/web/(\d{14})[a-z_]*/(.+)$")


def _snapshot_date(snapshot_url):
    m = SNAPSHOT_RE.match(snapshot_url or "")
    return f"{m[1][:4]}-{m[1][4:6]}-{m[1][6:8]}" if m else ""


def _latest_snapshot(url):
    """The URL of the latest Wayback Machine snapshot of url, or None."""
    raw, _, _ = _get(WAYBACK_API + urllib.parse.quote(url, safe=""))
    closest = (json.loads(raw).get("archived_snapshots") or {}).get("closest") or {}
    return closest.get("url") if closest.get("available") and SNAPSHOT_RE.match(closest.get("url", "")) else None


def _get_snapshot(snapshot_url):
    """The archived bytes as the site served them (the id_ form leaves out the Wayback Machine's toolbar)."""
    m = SNAPSHOT_RE.match(snapshot_url)
    if not m:
        raise ValueError(f"not a Wayback Machine snapshot URL: {snapshot_url}")
    return _get(f"https://web.archive.org/web/{m[1]}id_/{m[2]}")


def _save_page_now(url):
    """Ask the Wayback Machine to snapshot url now (Save Page Now); the snapshot's URL, or an exception."""
    req = urllib.request.Request("https://web.archive.org/save/" + url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        for cand in (r.geturl(), r.headers.get("Content-Location", ""), r.headers.get("Location", "")):
            cand = urllib.parse.urljoin("https://web.archive.org/", cand or "")
            if SNAPSHOT_RE.match(cand):
                return cand
    raise RuntimeError("Save Page Now gave no snapshot URL")


def _archiving():
    """EVIDENCE_ARCHIVE turns on snapshots of quoted pages; off by default, since it sends each URL to archive.org."""
    return os.environ.get("EVIDENCE_ARCHIVE", "").strip().lower() not in ("", "0", "off", "false", "no")


def _known_snapshot(meta):
    return meta.get("archive_url") or meta.get("snapshot_url")


def _save_snapshot(meta_file, meta):
    """Save Page Now for a fetched web page, recorded in its cache metadata so each page is sent once."""
    meta["snapshot_url"] = _save_page_now(meta["url"])
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta["snapshot_url"]


def _is_web_page(meta_file, meta):
    """A page `fetch` cached (not a pxweb query, a data script or a user's file, and never in sources/)."""
    return (str(meta.get("url", "")).startswith("http") and meta.get("kind") in ("html", "pdf", "text")
            and not meta.get("user_supplied") and "sources" not in Path(meta_file).resolve().parts)


def load_lines(path):
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        cached = path.with_suffix(".txt")
        if "sources" in path.resolve().parts:  # never write into the user's sources/; import the file instead
            return path, _pdf_to_paragraphs(path)
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
        txt, info = fetch_to_cache(a.folder, a.url, a.refresh, a.render, a.archive)
    except Exception as e:  # noqa: BLE001 - report any failure as one line
        print(f"FAILED {a.url}: {type(e).__name__}: {e}")
        hint = "" if a.render or a.archive else \
            " If the site is down, retry with --archive. If the page needs JavaScript, retry with --render."
        print(f"→{hint} If this source matters, raise an Evidence Request (paywall/blocked) or try another URL.")
        sys.exit(1)
    rel = txt.relative_to(Path(a.folder))
    flag = " (TLS certificate NOT verified)" if info.get("tls_unverified") else ""
    if info.get("archive_url"):
        flag += f" (archived {info['archived']}: {info['archive_url']})"
    print(f"cached: {rel}  [{info['kind']}, {info['paragraphs']} paragraphs, fetched {info['fetched']}]{flag}")
    if info.get("title"):
        print(f"title: {info['title']}")
    lines = txt.read_text(encoding="utf-8").splitlines()
    if not a.render and not a.archive and info["kind"] == "html" and sum(map(len, lines)) < 1500:
        print("note: very little text; if the page needs JavaScript, retry with --render.")
    print_hits(lines, a.keywords, a.max)
    if info.get("links"):
        ks = [norm(k, True) for k in a.keywords]
        links = [l for l in info["links"]
                 if DOC_LINK.search(l[1]) or any(k in norm(l[0] + " " + l[1], True) for k in ks)]
        print(f"== document links and links matching the keywords ({len(links)}{', first 25 shown' if len(links) > 25 else ''}); fetch one to read it:")
        for text, href in links[:25]:
            print(f"  {text[:80] or '(no text)'} -> {href}")


def cmd_import(a):
    src = Path(a.file).resolve()
    if not src.is_file():
        sys.exit(f"{a.file}: no such file")
    folder = Path(a.folder).resolve()
    files = folder / "evidence" / "files"
    files.mkdir(parents=True, exist_ok=True)
    name = "user-" + re.sub(r"[^a-zA-Z0-9]+", "-", re.sub(r"^user-", "", a.name)).strip("-")
    txt, meta = files / f"{name}.txt", files / f"{name}.json"
    if txt.exists() and not a.force:
        sys.exit(f"{txt.relative_to(folder)} exists; pick another --name (or --force)")
    raw = src.read_bytes()
    paras, title, kind = to_paragraphs(raw, "text/html" if src.suffix.lower() in (".html", ".htm") else "", files)
    txt.write_text("\n".join(paras) + "\n", encoding="utf-8")
    info = {"url": os.path.relpath(src, folder), "original": str(src), "fetched": datetime.date.today().isoformat(),
            "content_type": "", "kind": kind, "title": title, "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw), "paragraphs": len(paras), "user_supplied": True}
    meta.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"imported: {txt.relative_to(folder)}  [{kind}, {len(paras)} paragraphs] from {info['url']}")
    if title:
        print(f"title: {title}")
    if sum(map(len, paras)) < 1500:
        print("note: very little text; a scanned PDF needs OCR, a saved web page may need its live URL fetched with --render.")


def work_dir(folder):
    """The agent/ folder, given it or the project folder that holds it."""
    p = Path(folder)
    return p / "agent" if (p / "agent").is_dir() else p


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


# ---------- research papers (OpenAlex) ----------

OPENALEX = "https://api.openalex.org"


REVIEW_WORDS = 'review OR meta-analysis OR "meta analysis" OR meta-regression OR survey OR synthesis'


class BudgetSpent(Exception):
    """OpenAlex's daily budget (the key's, or the network's shared one without a key) is used up."""


_budget = {}  # X-RateLimit-* headers of the last OpenAlex response


def _openalex(path, params):
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        params = {**params, "api_key": key}
    url = f"{OPENALEX}{path}?{urllib.parse.urlencode(params)}" if params else f"{OPENALEX}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                _budget.update({k.lower(): v for k, v in r.headers.items() if k.lower().startswith("x-ratelimit-")})
                return json.loads(r.read(MAX_BYTES))
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            try:
                body = json.loads(e.read(MAX_BYTES))
            except ValueError:
                body = {}
            if body.get("reason") == "daily_budget" or body.get("error") == "not_enough_credits":
                raise BudgetSpent(e.headers.get("X-RateLimit-Reset"))
            if attempt == 3:  # a per-second limit: wait as told, then retry
                raise
            import time
            time.sleep(min(float(e.headers.get("Retry-After") or 1), 30))


def _hours(seconds):
    try:
        return f"in about {max(1, round(int(seconds) / 3600))} h"
    except (TypeError, ValueError):
        return "at midnight UTC"


def _budget_warning():
    """WARNING when less than a tenth of today's budget is left."""
    try:
        left, limit = int(_budget["x-ratelimit-remaining"]), int(_budget["x-ratelimit-limit"])
        per_search = int(_budget.get("x-ratelimit-credits-used") or 10) or 10
    except (KeyError, ValueError):
        return
    if left < limit / 10:
        whose = "this key's" if os.environ.get("OPENALEX_API_KEY") else "this network's shared"
        print(f"WARNING: OpenAlex budget low: {whose} budget has about {left // per_search} searches left today; "
              f"it resets {_hours(_budget.get('x-ratelimit-reset'))}. Search only for what your Claims need.")


def _work_kind(w):
    """article | review | preprint | book … with the venue type, and RETRACTED when it is."""
    src = (w.get("primary_location") or {}).get("source") or {}
    kind = w.get("type", "?")
    if kind == "article" and src.get("type") == "repository":
        kind = "preprint"
    return kind + (" · RETRACTED" if w.get("is_retracted") else "")


def _copies(w):
    seen, out = set(), []
    for loc in w.get("locations") or []:
        url = loc.get("pdf_url") or loc.get("landing_page_url")
        if not url or url in seen:
            continue
        seen.add(url)
        src = loc.get("source") or {}
        out.append((url, loc.get("version") or "version unknown", src.get("type") or "?",
                    "open" if loc.get("is_oa") else "closed"))
    return out


def _abstract(w):
    inv = w.get("abstract_inverted_index") or {}
    pos = sorted((i, word) for word, idx in inv.items() for i in idx)
    return " ".join(word for _, word in pos)


def cmd_papers(a):
    try:
        _papers(a)
        _budget_warning()
    except BudgetSpent as e:
        if os.environ.get("OPENALEX_API_KEY"):
            print(f"WARNING: OpenAlex budget used up: this key's daily budget is spent; it resets {_hours(str(e))}. "
                  "Until then, find papers with WebSearch and Google Scholar, and fetch them as usual.")
        else:
            print(f"WARNING: OpenAlex budget used up: the shared daily budget for this network is spent; it resets "
                  f"{_hours(str(e))}. Until then, find papers with WebSearch and Google Scholar. A free key "
                  "(https://openalex.org/settings/api, set as OPENALEX_API_KEY) has its own, ten times larger budget.")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        print(f"FAILED: HTTP {e.code} {e.read()[:300].decode('utf-8', 'replace')}")
        if e.code in (401, 403) and os.environ.get("OPENALEX_API_KEY"):
            print("WARNING: OpenAlex refused OPENALEX_API_KEY: check the key at https://openalex.org/settings/api.")
        sys.exit(1)
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        sys.exit(1)


NO_KEY = ("WARNING: OPENALEX_API_KEY is not set, so paper searches share one small free daily budget with everyone "
          "on this network, and can stop working mid-debate. A free key: https://openalex.org/settings/api; set it "
          "as OPENALEX_API_KEY (in Claude Code, under \"env\" in ~/.claude/settings.json) and start a new session.")


def _papers(a):
    if not os.environ.get("OPENALEX_API_KEY"):
        print(NO_KEY)
    if a.check:
        if os.environ.get("OPENALEX_API_KEY"):
            r = _openalex("/rate-limit", {})["rate_limit"]  # free: costs no budget
            left, total = r["daily_remaining_usd"], r["daily_budget_usd"]
            print(f"OPENALEX_API_KEY is set: {left / total:.0%} of today's budget left, "
                  f"about {round(left / 0.001)} searches; it resets {_hours(r.get('resets_in_seconds'))}.")
            if left < total / 10:
                print("WARNING: OpenAlex budget low: fewer than a tenth of today's searches are left.")
        return
    if not a.words:
        sys.exit("usage: papers <words …> | <DOI>   (or --check)")
    q = " ".join(a.words).strip()
    one = re.match(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)?(10\.\S+)$", q, re.I) or re.match(r"^(W\d+)$", q)
    if one:
        ident = one.group(1)
        w = _openalex(f"/works/{'doi:' + ident if ident.startswith('10.') else ident}", {})
        venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name", "no venue")
        authors = [x["author"]["display_name"] for x in w.get("authorships", [])]
        print(f"{w['display_name']}\n{w.get('publication_date', w.get('publication_year'))} · {_work_kind(w)} · {venue}"
              f" · cited {w.get('cited_by_count', 0)} · {w.get('doi') or w['id']}")
        print("authors: " + (", ".join(authors[:8]) + (f" … (+{len(authors) - 8})" if len(authors) > 8 else "") or "unknown"))
        funders = [f.get("display_name", "") for f in w.get("funders") or []]
        print("funders: " + (", ".join(funders) if funders else "none recorded (read the paper's acknowledgements)"))
        print("copies (fetch the published version where you can):")
        for url, ver, st, oa in _copies(w) or [("none listed", "", "", "")]:
            print(f"  - {url}  [{ver}, {st}, {oa}]")
        ab = _abstract(w)
        print("abstract: " + (ab[:1500] + (" …" if len(ab) > 1500 else "") if ab else "none in OpenAlex"))
        return
    filters = []
    if a.since:
        filters.append(f"publication_year:>{a.since - 1}")
    if a.reviews:  # by title, not type:review: economics reviews are typed "article", and type:review is mostly medicine
        filters += [f"title.search:({REVIEW_WORDS})", "type:!dataset", "type:!book-review"]
    if a.open:
        filters.append("is_oa:true")
    params = {"search": q, "per-page": a.max,
              "select": "id,doi,display_name,publication_year,type,cited_by_count,is_retracted,"
                        "primary_location,locations"}
    if filters:
        params["filter"] = ",".join(filters)
    res = _openalex("/works", params)
    print(f"{res['meta']['count']} work(s) for '{q}', {len(res['results'])} shown")
    for w in res["results"]:
        venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name", "no venue")
        doi = (w.get("doi") or "").replace("https://doi.org/", "") or w["id"].rsplit("/", 1)[-1]
        opens = [f"{u} [{v}]" for u, v, _, oa in _copies(w) if oa == "open"]
        print(f"- {w.get('publication_year')} · {_work_kind(w)} · cited {w.get('cited_by_count', 0)} · {venue} · {doi}\n"
              f"  {w['display_name']}\n  open copy: {opens[0] if opens else 'none listed'}")


# ---------- data scripts (statistics through a Python library: sistat, wbgapi, sdmx1, …) ----------

_DEPS = re.compile(r"^# /// script$(.*?)^# ///$", re.S | re.M)


def _script_deps(text):
    block = _DEPS.search(text)
    if not block:
        return None
    body = "\n".join(ln[2:] if ln.startswith("# ") else ln.lstrip("#") for ln in block.group(1).splitlines())
    m = re.search(r"dependencies\s*=\s*\[(.*?)\]", body, re.S)
    return re.findall(r"[\"']([^\"']+)[\"']", m.group(1)) if m else []


def _run_data_script(script):
    """Run a PEP 723 script with uv; its last stdout line is {"title", "url", "rows": [{col: value}, …]}."""
    r = subprocess.run(["uv", "run", "--quiet", "--script", str(script)], capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise RuntimeError(f"script failed: {(r.stderr or r.stdout).strip()[-600:]}")
    last = next((ln for ln in reversed(r.stdout.splitlines()) if ln.strip()), "")
    try:
        out = json.loads(last)
    except json.JSONDecodeError:
        raise RuntimeError("the script's last line of output is not JSON: end it with "
                           "print(json.dumps({'title': …, 'url': …, 'rows': rows}, ensure_ascii=False))")
    rows = out.get("rows") if isinstance(out, dict) else None
    if not rows or not isinstance(rows, list) or not all(isinstance(x, dict) for x in rows):
        raise RuntimeError("the JSON needs 'rows': a non-empty list of objects, one per data row")
    if not str(out.get("url", "")).startswith("http"):
        raise RuntimeError("the JSON needs 'url': the dataset's public page or API query URL (http…)")
    return out, last


def _data_rows(rows):
    """Records -> header line + one self-describing paragraph per row, as pxweb fetch writes them."""
    head = list(dict.fromkeys(k for row in rows for k in row))

    def fmt(v):
        if v is None or (isinstance(v, float) and v != v):
            return ""
        return format(v, "g") if isinstance(v, float) and v.is_integer() and abs(v) < 1e15 else str(v)
    return [" | ".join(head)] + [" | ".join(f"{k}: {fmt(row.get(k))}" for k in head) for row in rows]


def cmd_data(a):
    folder, script = Path(a.folder), Path(a.script).resolve()
    if not script.exists():
        sys.exit(f"no script {a.script}")
    text = script.read_text(encoding="utf-8")
    deps = _script_deps(text)
    if deps is None:
        sys.exit("the script needs a `# /// script` block listing its dependencies (see reference/statistics.md)")
    loose = [d for d in deps if "==" not in d]
    if loose:
        sys.exit(f"pin every dependency to an exact version, so the Audit re-runs the same code: {', '.join(loose)}")
    dest = folder / "evidence" / "files" / "data"
    dest.mkdir(parents=True, exist_ok=True)
    kept = dest / script.name
    if kept.resolve() != script:
        if kept.exists() and kept.read_text(encoding="utf-8") != text:
            sys.exit(f"{kept.relative_to(folder)} exists with other code: rename your script")
        kept.write_text(text, encoding="utf-8")
    txt, meta = kept.with_suffix(".txt"), kept.with_suffix(".json")
    if txt.exists() and meta.exists() and not a.refresh and \
            json.loads(meta.read_text(encoding="utf-8")).get("script_sha256") == hashlib.sha256(text.encode()).hexdigest():
        info = json.loads(meta.read_text(encoding="utf-8"))
    else:
        try:
            out, raw = _run_data_script(kept)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            print(f"FAILED: {e}")
            sys.exit(1)
        paras = _data_rows(out["rows"])
        txt.write_text("\n".join(paras) + "\n", encoding="utf-8")
        info = {"url": out["url"], "fetched": datetime.date.today().isoformat(), "content_type": "application/json",
                "kind": "data", "title": out.get("title", ""), "script": str(kept.relative_to(folder)),
                "script_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "sha256": hashlib.sha256(raw.encode()).hexdigest(), "bytes": len(raw.encode()),
                "paragraphs": len(paras), "tls_unverified": False}
        meta.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"cached: {txt.relative_to(folder)}  [data, {info['paragraphs'] - 1} rows]  {info['title']}  <{info['url']}>")
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
    snapshot, queued = (_known_snapshot(meta) if url == meta.get("url") else None), None
    if not snapshot and url == meta.get("url") and _archiving() and _is_web_page(meta_file, meta):
        try:
            snapshot = _save_snapshot(meta_file, meta)
        except Exception as err:  # noqa: BLE001 - Save Page Now is rate-limited; the quote stands without it
            queued = f"{type(err).__name__}: {str(err)[:80]}"

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
        *([f"archive_url: {snapshot}"] if snapshot else []),
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
    if queued:
        print(f"note: no archive snapshot yet ({queued}); `evidence.py archive <folder>` retries it later.")


ARCHIVE_PAUSE = 6  # seconds between Save Page Now requests: anonymous use is limited to a few a minute


def cmd_archive(a):
    """Snapshot every quoted web page that has none yet, and record it as archive_url in its Evidence."""
    if not _archiving():
        sys.exit("EVIDENCE_ARCHIVE is off: set EVIDENCE_ARCHIVE=1 to send quoted URLs to the Wayback Machine.")
    folder = Path(a.folder)
    waiting = {}  # source metadata file -> Evidence files that quote it without a snapshot
    for f in sorted((folder / "evidence").glob("E-*.md")):
        fm = _front(f.read_text(encoding="utf-8"))
        if fm.get("archive_url") or not fm.get("source_file"):
            continue
        meta_file = (folder / fm["source_file"]).with_suffix(".json")
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if _is_web_page(meta_file, meta) and fm.get("url") == meta["url"]:
                waiting.setdefault(meta_file, []).append(f)
    saved = failed = 0
    for n, (meta_file, evs) in enumerate(waiting.items()):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        snapshot = _known_snapshot(meta)
        if not snapshot:
            if n:
                time.sleep(ARCHIVE_PAUSE)
            try:
                snapshot = _save_snapshot(meta_file, meta)
            except Exception as e:  # noqa: BLE001
                failed += len(evs)
                print(f"FAILED {meta['url']}: {type(e).__name__}: {str(e)[:80]} ({', '.join(f.stem for f in evs)})")
                if isinstance(e, urllib.error.HTTPError) and e.code == 429:
                    print("→ Save Page Now is rate-limiting: run archive again in a few minutes.")
                    break
                continue
        for f in evs:
            text = f.read_text(encoding="utf-8")
            f.write_text(re.sub(r"\A(---\n.*?\n)(---\n)", lambda m: f"{m[1]}archive_url: {snapshot}\n{m[2]}",
                                text, count=1, flags=re.S), encoding="utf-8")
            saved += 1
        print(f"{snapshot}  {', '.join(f.stem for f in evs)}")
    left = sum(map(len, waiting.values())) - saved
    print(f"{saved} Evidence given a snapshot" + (f", {left} still waiting" if left else "") + ".")


# ---------- calc: arithmetic over Evidence ----------

CALC_OPERAND = re.compile(r"\b(E-(?:PRIMARY|USER|PRO|CON)(?:-[A-Z])?-\d{3}):(\d+(?:\.\d+)?)\b")
CALC_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.Pow: operator.pow}


def _calc_result(formula):
    """(result, [(id, value text)], [constant text], shown formula) of a calc formula, or ValueError.

    An operand is <Evidence ID>:<number as a plain decimal>; any other number is a constant."""
    operands = []

    def placeholder(m):
        operands.append((m[1], m[2]))
        return f"_v{len(operands) - 1}"
    expr = CALC_OPERAND.sub(placeholder, formula.replace("×", "*").replace("÷", "/").replace("−", "-"))
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"not a formula: {e.msg}") from None
    constants = []

    def ev(node):
        if isinstance(node, ast.BinOp) and type(node.op) in CALC_OPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("exponent above 100")
            try:
                return CALC_OPS[type(node.op)](left, right)
            except (ZeroDivisionError, decimal.InvalidOperation):
                raise ValueError("division by zero") from None
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.Name) and re.fullmatch(r"_v\d+", node.id):
            return decimal.Decimal(operands[int(node.id[2:])][1])
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            text = ast.get_source_segment(expr, node)
            constants.append(text)
            return decimal.Decimal(text)
        raise ValueError(f"only numbers, Evidence operands (E-PRO-003:1234.5), + - * / ** and brackets are allowed, "
                         f"not {ast.get_source_segment(expr, node) or type(node).__name__}")
    with decimal.localcontext() as ctx:
        ctx.prec = 28
        result = ev(tree.body)
    if not operands:
        raise ValueError("the formula uses no Evidence: write each input as <Evidence ID>:<number>")
    shown = re.sub(r"_v(\d+)", lambda m: operands[int(m[1])][1], expr)
    return result, operands, constants, shown


def _calc_fmt(d):
    """A result to 6 significant digits, never fewer than its whole part."""
    q = d.quantize(decimal.Decimal(1).scaleb(min(0, d.adjusted() - 5)), rounding=decimal.ROUND_HALF_UP)
    s = format(q, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def _calc_inputs(folder, operands):
    """For each operand, where its value stands in that Evidence's Quote or Context, or a problem."""
    import numcheck
    found, problems = [], []
    for eid, val in operands:
        p = folder / "evidence" / f"{eid}.md"
        if not p.exists():
            problems.append(f"{eid} does not exist")
            continue
        text = p.read_text(encoding="utf-8")
        if re.search(r"^- Result:\s*failed", text, re.M | re.I):
            problems.append(f"{eid} failed the Audit")
        v, hit = decimal.Decimal(val), None
        for name in ("Quote", "Context"):
            body = numcheck.section(text, name)
            for n in numcheck.numbers(body, quantities_only=False):
                if any(abs(pv) == v or abs(pv) * n.scale == v for pv, _ in n.values):
                    hit = f"{name}: …{body[max(0, n.start - 70):n.start + len(n.text) + 50].strip()}…"
                    break
            if hit:
                break
        if hit:
            found.append((eid, val, hit))
        else:
            problems.append(f"{val} is not in the Quote or Context of {eid}")
    return found, problems


def cmd_calc(a):
    folder = Path(a.folder)
    out = folder / "evidence" / f"{a.id}.md"
    if out.exists() and not a.force:
        sys.exit(f"{out} exists; pick the next free ID (or --force to overwrite your own file)")
    try:
        result, operands, constants, shown = _calc_result(a.formula)
    except ValueError as e:
        sys.exit(f"FAILED: {e}")
    found, problems = _calc_inputs(folder, operands)
    if problems:
        sys.exit("FAILED: " + "; ".join(problems) + ". Copy each input from its Evidence as a plain decimal "
                 "(36,83 % → 36.83; 1.195 mio → 1195), or quote the Evidence that states it first.")
    res = _calc_fmt(result)
    today = datetime.date.today().isoformat()
    inputs = list(dict.fromkeys(e for e, _ in operands))
    parts = [
        "---", f"id: {a.id}", f"added_by: {a.added_by}", f"stage: {a.stage}", "kind: calc",
        f"url: evidence/{a.id}.md", f"accessed: {today}", f"title: {a.title}", f"author: {a.added_by}",
        "publisher: evidence.py calc", f"published: {today}", "language: n/a",
        f"formula: {a.formula}", f"inputs: {', '.join(inputs)}", f"result: {res}", "---", "",
        "## Quote", "", f"> {shown} = {res}", "", "## Inputs", "",
        f"Method: {a.method}", "",
        *[f"- {val} from {eid} ({hit})" for eid, val, hit in found],
        *([f"- Constants: {', '.join(dict.fromkeys(constants))}"] if constants else []), "",
        "## Audit", "", "- Quote found:", "- Supports:", "- Cherry-picked:", "- Source Tier:",
        "- Funder/affiliation:", "- Notes:", "",
    ]
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote evidence/{a.id}.md: {shown} = {res}")


def _calc_verify(folder, fm):
    """recomputed | differs: … | input: … for a calc Evidence file."""
    try:
        result, operands, _, _ = _calc_result(fm.get("formula", ""))
    except ValueError as e:
        return f"formula: {e}"
    _, problems = _calc_inputs(folder, operands)
    if problems:
        return "input: " + "; ".join(problems)
    res = _calc_fmt(result)
    return "recomputed" if res == fm.get("result") else f"differs: now {res}, file says {fm.get('result')}"


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


def _live_paras(folder, url, pq, pscript, rendered):
    """(paragraphs, notes, sha256 of the downloaded bytes) for the live source, or (the exception, [], None).

    The hash is given only for a plain download, the one case where the cache stores the same bytes."""
    try:
        with tempfile.TemporaryDirectory() as td:
            if pscript:
                return _data_rows(_run_data_script(folder / pscript)[0]["rows"]), ["re-ran script"], None
            if pq:
                raw, ctype = _px_json(url, pq)
                return _px_rows(raw, ctype), ["re-queried"], None
            if rendered:
                raw, ctype, _ = _render(url)
                return to_paragraphs(raw, ctype, td)[0], ["re-rendered"], None
            raw, ctype, insecure = _get(url)
            return (to_paragraphs(raw, ctype, td)[0], ["TLS unverified"] if insecure else [],
                    hashlib.sha256(raw).hexdigest())
    except Exception as e:  # noqa: BLE001
        return e, [], None


def _archived_paras(url, snapshot_url):
    """(paragraphs, snapshot URL) of the given snapshot, or else of the latest one, or (the exception, None)."""
    try:
        snapshot_url = snapshot_url or _latest_snapshot(url)
        if not snapshot_url:
            raise LookupError("no archived copy")
        raw, ctype, _ = _get_snapshot(snapshot_url)
        with tempfile.TemporaryDirectory() as td:
            return to_paragraphs(raw, ctype, td)[0], snapshot_url
    except Exception as e:  # noqa: BLE001
        return e, None


def cmd_verify(a):
    folder = Path(a.folder)
    files = sorted((folder / "evidence").glob("E-*.md"))
    if a.ids:
        want = set(a.ids)
        files = [f for f in files if f.stem in want]
    print("| Evidence | cached copy | live source | note |\n|---|---|---|---|")
    sources = {}
    for f in files:
        text = f.read_text(encoding="utf-8")
        fm, quote = _front(text), _section(text, "Quote")
        if not quote:
            print(f"| {f.stem} | no quote | — | Quote section empty |")
            continue
        if fm.get("kind") == "calc":
            print(f"| {f.stem} | {_calc_verify(folder, fm)} | — | calc: {fm.get('formula', '')} |")
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
            rendered = bool(src) and src.endswith("-rendered.txt")
            pmeta = (folder / src).with_suffix(".json") if src else None
            pinfo = json.loads(pmeta.read_text(encoding="utf-8")) if pmeta and pmeta.exists() else {}
            pq, pscript = pinfo.get("post_query"), pinfo.get("script")
            key = (url, pscript, json.dumps(pq, sort_keys=True), rendered)
            if key not in sources:  # many Evidence quote one source: download it once per run
                sources[key] = _live_paras(folder, url, pq, pscript, rendered)
            paras, how, sha = sources[key]
            if isinstance(paras, Exception) and not (pq or pscript):  # a web page: try the Wayback Machine
                akey = ("archive", url, fm.get("archive_url"))
                if akey not in sources:
                    sources[akey] = _archived_paras(url, fm.get("archive_url"))
                apara, snap = sources[akey]
                note.append(f"live: {type(paras).__name__}: {str(paras)[:60]}")
                if isinstance(apara, Exception):
                    live = "unreachable"
                    note.append(f"archive: {type(apara).__name__}: {str(apara)[:60]}")
                else:
                    live = f"archived {_snapshot_date(snap)}: {match_quality(quote, norm(' '.join(apara)))}"
                    note.append(f"archive: {snap}")
            elif isinstance(paras, Exception):
                live = "unreachable"
                note.append(f"{type(paras).__name__}: {str(paras)[:60]}")
            elif sha and sha == pinfo.get("sha256"):
                # the same bytes the quote was cut from: a text match would only test the extraction again
                live = "unchanged"
                note += how
            else:
                live = match_quality(quote, norm(" ".join(paras)))
                note += how
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
    p.add_argument("--archive", action="store_true", help="the latest Wayback Machine snapshot instead (site down)")
    p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser("import", help="extract the text of a user-supplied file into evidence/files/user-<name>.txt")
    p.add_argument("folder")
    p.add_argument("file", help="the original, normally in the project's sources/ folder")
    p.add_argument("--name", required=True, help="short slug for the cached text (user- is prefixed)")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_import)
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

    p = sub.add_parser("papers", help="find research papers in OpenAlex, or look one up by DOI")
    p.add_argument("words", nargs="*", help="search words, or one DOI / OpenAlex id for the paper's details")
    p.add_argument("--check", action="store_true", help="only say whether OPENALEX_API_KEY is set")
    p.add_argument("--since", type=int, help="published in this year or later")
    p.add_argument("--reviews", action="store_true", help="only reviews: a review, meta-analysis, meta-regression, survey or synthesis in the title")
    p.add_argument("--open", action="store_true", help="only papers with an open-access copy")
    p.add_argument("--max", type=int, default=10, help="papers to list (default 10)")
    p.set_defaults(fn=cmd_papers)

    p = sub.add_parser("data", help="run a pinned stats script (sistat, wbgapi, sdmx1 …) and cache its rows as text")
    p.add_argument("folder")
    p.add_argument("script", help="PEP 723 script; its last output line is JSON {title, url, rows}")
    p.add_argument("--max", type=int, default=20, help="rows to print (default 20)")
    p.add_argument("--refresh", action="store_true", help="re-run even if the script is unchanged")
    p.set_defaults(fn=cmd_data)

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

    p = sub.add_parser("calc", help="write an Evidence file that computes a number from numbers in other Evidence")
    p.add_argument("folder")
    p.add_argument("formula", help='e.g. "E-CON-B-040:5159.12 / (1 - E-PRO-B-046:36.83 / 100)"')
    p.add_argument("--id", required=True)
    p.add_argument("--added-by", required=True)
    p.add_argument("--stage", required=True)
    p.add_argument("--title", required=True, help="what the result is, e.g. 'Gross wage at which the cap starts, EUR a month'")
    p.add_argument("--method", required=True, help="one or two sentences: what each input is, and why the formula combines them so")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_calc)

    p = sub.add_parser("archive", help="snapshot quoted web pages in the Wayback Machine (needs EVIDENCE_ARCHIVE=1)")
    p.add_argument("folder")
    p.set_defaults(fn=cmd_archive)

    p = sub.add_parser("verify", help="check Evidence quotes against cached and/or live sources")
    p.add_argument("folder")
    p.add_argument("ids", nargs="*")
    p.add_argument("--live", action="store_true", help="also re-download every http source")
    p.set_defaults(fn=cmd_verify)

    a = ap.parse_args()
    if getattr(a, "folder", None):
        a.folder = str(work_dir(a.folder))
    a.fn(a)


if __name__ == "__main__":
    main()
