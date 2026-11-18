# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.65.2"]
# ///
"""Render a JavaScript page in headless Chromium and print it as JSON on stdout.

Usage: uv run --script render.py <url> [--wait-ms 3000]
Output: {"url": <final url>, "status": <http status>, "html": <rendered html>, "links": [[text, href], ...]}

Called by evidence.py fetch --render. Uses Playwright's own browser if installed, otherwise any
Chromium already in ~/.cache/ms-playwright, otherwise asks for `playwright install chromium-headless-shell`.
"""
import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def fallback_executables():
    root = Path.home() / ".cache" / "ms-playwright"
    found = sorted(root.glob("chromium_headless_shell-*/*/chrome-headless-shell"), reverse=True)
    found += sorted(root.glob("chromium-*/chrome-linux*/chrome"), reverse=True)
    return [str(p) for p in found]


def launch(p):
    try:
        return p.chromium.launch()
    except Error as e:
        if "Executable doesn't exist" not in str(e):
            raise
    for exe in fallback_executables():
        try:
            return p.chromium.launch(executable_path=exe)
        except Error:
            continue
    sys.exit("No Chromium found. Run: uv run --with playwright==1.65.2 playwright install chromium-headless-shell")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--wait-ms", type=int, default=3000, help="extra wait after network idle (default 3000)")
    a = ap.parse_args()
    with sync_playwright() as p:
        browser = launch(p)
        ctx = browser.new_context(user_agent=UA, ignore_https_errors=True, locale="sl-SI")
        page = ctx.new_page()
        resp = page.goto(a.url, wait_until="domcontentloaded", timeout=60_000)
        try:
            page.wait_for_load_state("networkidle", timeout=20_000)
        except Error:
            pass
        page.wait_for_timeout(a.wait_ms)
        # Plain links, plus links opened from onclick="window.open('…')" (e.g. dz-rs.si attachments).
        links = page.eval_on_selector_all("a[href], [onclick]", """els => els.flatMap(e => {
            const text = (e.innerText || "").trim().slice(0, 120);
            const out = [];
            if (e.href && !e.href.endsWith("#")) out.push([text, e.href]);
            const m = (e.getAttribute("onclick") || "").match(/window\\.open\\(\\s*['"]([^'"]+)['"]/);
            if (m) out.push([text, new URL(m[1].replace(/&amp;/g, "&"), document.baseURI).href]);
            return out;
        })""")
        json.dump({"url": page.url, "status": resp.status if resp else None,
                   "html": page.content(), "links": links}, sys.stdout, ensure_ascii=False)
        browser.close()


if __name__ == "__main__":
    main()
