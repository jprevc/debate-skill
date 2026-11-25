"""evidence.py lawdiff: a bill's amending articles lined up with the consolidated law they amend, before and after.

Run: uv run --with markdown==3.7 --with pytest==9.2.0 pytest tests
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "debate" / "scripts"

# A consolidated law as a rendered PIS page caches it: one paragraph per line, with site noise around the articles
# and the amending acts' own provisions after the last article.
LAW = """Skoči do osrednje vsebine
ZAKO9999
ZAKON o pokojninah (ZPok-2)
I. SPLOŠNE DOLOČBE
1. člen
(vsebina)
Ta zakon ureja pokojnine.
2. člen
Sodna praksa Vrhovnega sodišča
(najnižja pokojnina)
Opomba: Spremenjeni 2. člen se uporablja od 1. januarja 2025.
(1) Najnižja pokojnina znaša 500 eurov.
(2) Zavarovancu, ki uveljavi predčasne ali starostne pokojnine, se pokojnina usklajuje.
(3) Znesek se usklajuje:
- januarja in
- julija.
(4) Podatke sporoči zavod.
II. POSEBNE DOLOČBE
3. člen
(delna pokojnina)
(1) Delno pokojnino lahko dobi, kdor dela ali starostne ure ali starostne dni.
(2) Delna pokojnina znaša polovico.
3.a člen
(izplačilo dela pokojnine)
Zavarovancu se izplača 40 % pokojnine.
4. člen
(stopnja)
Stopnja znaša 25 % in se šteje kot dokončni davek.
2020-01-2448Zakon o spremembah Zakona o pokojninah (ZPok-2A)139/20
PREHODNE IN KONČNE DOLOČBE
2. člen
Ta zakon začne veljati naslednji dan.
"""

# A bill as `import` caches its PDF: headings run into the paragraph before, and paragraphs break mid-sentence.
BILL = """ZAKON
O UKREPIH (ZUK)
PRVI DEL
1. člen
(vsebina)
S tem zakonom se spreminja Zakon o pokojninah.
DRUGI DEL
1. ZAKON O POKOJNINAH
2. člen
V Zakonu o pokojninah (Uradni list RS, št. 1/20 – uradno prečiščeno besedilo in 2/21 – odl. US) se 2. člen spremeni tako, da se glasi:
»2. člen
(najnižja pokojnina)
(1) Najnižja pokojnina znaša 600 eurov. (2) Zavarovancu se pokojnina usklajuje.
(3) Znesek se usklajuje januarja.«.
3. člen
3.a člen se črta.
4. člen
Za 3.a členom se doda nov 3.b člen, ki se glasi:
»3.b člen
(dvojni status)
(1) Zavarovanec ima hkrati dva statusa. (2) Izplača se mu 100 % pokojnine.«. 2. ZAKON O DAVKIH
5. člen
V Zakonu o davkih (Uradni list RS, št. 9/09) se 7. člen črta.
TRETJI DEL
6. člen
(prehodna določba)
Spremenjeni 2. člen ZPok-2 se uporablja od 1. januarja 2027.
"""


CITE = "V Zakonu o pokojninah (Uradni list RS, št. 1/20 in 2/21 – odl. US) se"


def bill(*articles):
    """A bill whose 2., 3. … člen are the given amending texts (the first one cites the law with CITE)."""
    body = "\n".join(f"{n}. člen\n{t}" for n, t in enumerate(articles, 2))
    return f"ZAKON O UKREPIH (ZUK)\n1. ZAKON O POKOJNINAH\n{body}\n"


class Lawdiff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "agent"
        files = self.folder / "evidence" / "files"
        (files / "web").mkdir(parents=True)
        self.law = files / "web" / "pisrs-si-pregledPredpisa-id-ZAKO9999-rendered.txt"
        self.law.write_text(LAW, encoding="utf-8")
        self.law.with_suffix(".json").write_text(json.dumps(
            {"url": "https://pisrs.si/pregledPredpisa?id=ZAKO9999", "title": "Zakon o pokojninah (ZPok-2) (PISRS)",
             "fetched": "2026-11-20", "kind": "html"}), encoding="utf-8")
        self.bill = files / "user-zuk.txt"
        self.write_bill(BILL)

    def tearDown(self):
        self.tmp.cleanup()

    def write_bill(self, text):
        self.bill.write_text(text, encoding="utf-8")
        self.bill.with_suffix(".json").write_text(json.dumps(
            {"url": "../sources/zuk.pdf", "title": "", "kind": "pdf", "user_supplied": True}), encoding="utf-8")

    def run_ev(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "evidence.py"), *args], capture_output=True, text=True)

    def lawdiff(self, *extra):
        r = self.run_ev("lawdiff", str(self.folder), str(self.bill), str(self.law), *extra)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = self.folder / "evidence" / "files" / "lawdiff" / "ZPok-2-ZUK.txt"
        return r.stdout, out.read_text(encoding="utf-8").splitlines()

    def version(self, lines, article, label):
        """The paragraph after the line starting with `label` in the block of the law's `article`."""
        start = next(i for i, ln in enumerate(lines) if ln.startswith(f"== {article} ZPok-2"))
        i = next(i for i in range(start + 1, len(lines)) if lines[i].startswith(label))
        return lines[i + 1]

    def test_a_replaced_article_shows_the_consolidated_text_before_and_the_bills_text_after(self):
        out, lines = self.lawdiff()
        self.assertEqual(self.version(lines, "2. člen", "before:"),
                         "2. člen (najnižja pokojnina) (1) Najnižja pokojnina znaša 500 eurov. "
                         "(2) Zavarovancu, ki uveljavi predčasne ali starostne pokojnine, se pokojnina usklajuje. "
                         "(3) Znesek se usklajuje: - januarja in - julija. (4) Podatke sporoči zavod.")
        self.assertEqual(self.version(lines, "2. člen", "after:"),
                         "2. člen (najnižja pokojnina) (1) Najnižja pokojnina znaša 600 eurov. "
                         "(2) Zavarovancu se pokojnina usklajuje. (3) Znesek se usklajuje januarja.")
        self.assertIn("== 2. člen ZPok-2, amended by 2. člen ZUK: parsed", lines)

    def test_a_deleted_article_has_no_after_and_a_new_one_no_before(self):
        _, lines = self.lawdiff()
        self.assertEqual(self.version(lines, "3.a člen", "before:"),
                         "3.a člen (izplačilo dela pokojnine) Zavarovancu se izplača 40 % pokojnine.")
        self.assertEqual(self.version(lines, "3.a člen", "after:"), "(deleted)")
        self.assertEqual(self.version(lines, "3.b člen", "before:"), "(none: a new article)")
        self.assertEqual(self.version(lines, "3.b člen", "after:"),
                         "3.b člen (dvojni status) (1) Zavarovanec ima hkrati dva statusa. (2) Izplača se mu 100 % pokojnine.")
        self.assertIn("== 3.b člen ZPok-2, added by 4. člen ZUK: parsed", lines)

    def test_only_the_bills_section_on_this_law_is_used(self):
        out, lines = self.lawdiff()
        headers = [ln for ln in lines if ln.startswith("== ")]
        self.assertEqual(len(headers), 3, headers)  # 2., 3.a, 3.b: not the other act's 5. člen, not the transitional 6.
        self.assertIn("3 of 3 amending articles parsed", out)

    def test_an_article_it_cannot_apply_is_shown_as_both_full_texts(self):
        self.write_bill(BILL.replace("2. ZAKON O DAVKIH", "4.a člen\nV 4. členu se stavek prestavi na konec. 2. ZAKON O DAVKIH"))
        out, lines = self.lawdiff()
        self.assertIn("4. člen: unparsed (by 4.a člen)", out)
        self.assertIn("3 of 4 amending articles parsed", out)
        i = next(i for i, ln in enumerate(lines) if ln.startswith("== 4. člen ZPok-2, amended by 4.a člen ZUK: unparsed"))
        self.assertEqual(lines[i + 1:i + 5], [
            "current article: 4. člen ZPok-2 in force", "4. člen (stopnja) Stopnja znaša 25 % in se šteje kot dokončni davek.",
            "amending article: 4.a člen ZUK", "4.a člen V 4. členu se stavek prestavi na konec."])

    def test_words_and_paragraphs_are_struck_out_and_the_rest_renumbered(self):
        self.write_bill(bill(f"{CITE} v 2. členu v drugem odstavku črta besedilo »predčasne ali«.\n"
                             "Tretji odstavek se črta.\nDosedanji četrti odstavek postane tretji odstavek."))
        _, lines = self.lawdiff()
        self.assertEqual(self.version(lines, "2. člen", "after:"),
                         "2. člen (najnižja pokojnina) (1) Najnižja pokojnina znaša 500 eurov. "
                         "(2) Zavarovancu, ki uveljavi starostne pokojnine, se pokojnina usklajuje. "
                         "(3) Podatke sporoči zavod.")

    def test_a_paragraph_is_replaced_and_a_new_one_added_after_it(self):
        self.write_bill(bill(f"{CITE} v 3. členu prvi odstavek spremeni tako, da se glasi:\n"
                             "»(1) Delno pokojnino dobi, kdor dela.«.\n"
                             "Za prvim odstavkom se doda nov drugi odstavek, ki se glasi:\n»(2) Nov odstavek.«.\n"
                             "Dosedanji drugi odstavek postane tretji odstavek."))
        _, lines = self.lawdiff()
        self.assertEqual(self.version(lines, "3. člen", "after:"),
                         "3. člen (delna pokojnina) (1) Delno pokojnino dobi, kdor dela. (2) Nov odstavek. "
                         "(3) Delna pokojnina znaša polovico.")

    def test_words_that_stand_more_than_once_in_the_paragraph_are_left_unparsed(self):
        self.write_bill(bill(f"{CITE} v 3. členu v prvem odstavku črtata besedi »ali starostne«."))
        out, _ = self.lawdiff()
        self.assertIn("3. člen: unparsed (by 2. člen): »ali starostne« stands 2 times in the 1st paragraph", out)

    def test_words_are_replaced_and_an_unnumbered_article_gets_numbered_paragraphs(self):
        self.write_bill(bill(f"{CITE} v 4. členu v besedilu člena, ki se označi kot prvi odstavek, stopnja »25 %« "
                             "nadomesti s stopnjo »15 %«.\nZa prvim odstavkom se doda nov drugi odstavek, ki se glasi:\n"
                             "»(2) Za najem mladim je stopnja 5 %.«.",
                             "V 3. členu se v naslovu člena beseda »delna« nadomesti z besedo »polovična«."))
        out, lines = self.lawdiff()
        self.assertEqual(self.version(lines, "4. člen", "after:"),
                         "4. člen (stopnja) (1) Stopnja znaša 15 % in se šteje kot dokončni davek. "
                         "(2) Za najem mladim je stopnja 5 %.")
        self.assertTrue(self.version(lines, "3. člen", "after:").startswith("3. člen (polovična pokojnina) (1)"))
        self.assertIn("2 of 2 amending articles parsed", out)

    def test_articles_picks_the_amending_articles_when_the_bill_names_the_law_otherwise(self):
        self.write_bill(BILL.replace("V Zakonu o pokojninah", "V Zakonu o pokojninskem zavarovanju"))
        r = self.run_ev("lawdiff", str(self.folder), str(self.bill), str(self.law))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--articles", r.stdout + r.stderr)
        out, lines = self.lawdiff("--articles", "3,4")
        self.assertEqual([ln for ln in lines if ln.startswith("== ")],
                         ["== 3.a člen ZPok-2, amended by 3. člen ZUK: parsed", "== 3.b člen ZPok-2, added by 4. člen ZUK: parsed"])

    def test_quote_cites_a_version_and_the_quote_points_at_the_consolidated_law(self):
        _, lines = self.lawdiff()
        n = next(i for i, ln in enumerate(lines) if ln.startswith("before:")) + 2  # paragraph number of the text
        r = self.run_ev("quote", str(self.folder), str(self.folder / "evidence/files/lawdiff/ZPok-2-ZUK.txt"), str(n),
                        "--id", "E-PRO-001", "--added-by", "PRO", "--stage", "opening", "--title", "ZPok-2, 2. člen",
                        "--publisher", "PIS", "--language", "sl", "--from", "(1)", "--to", "500 eurov.")
        self.assertEqual(r.returncode, 0, r.stderr)
        ev = (self.folder / "evidence" / "E-PRO-001.md").read_text(encoding="utf-8")
        self.assertIn("url: https://pisrs.si/pregledPredpisa?id=ZAKO9999", ev)
        self.assertIn("> (1) Najnižja pokojnina znaša 500 eurov.", ev)
        self.assertIn("source_file: evidence/files/lawdiff/ZPok-2-ZUK.txt", ev)
        self.assertIn("> before: 2. člen ZPok-2 in force", ev)  # the context names the version quoted
        r = self.run_ev("verify", str(self.folder), "E-PRO-001")
        self.assertIn("| E-PRO-001 | exact |", r.stdout)

    def test_renumbering_that_disagrees_with_the_bill_is_left_unparsed(self):
        self.write_bill(bill(f"{CITE} v 2. členu tretji odstavek črta.\nDosedanji četrti odstavek postane peti odstavek."))
        out, _ = self.lawdiff()
        self.assertIn("2. člen: unparsed (by 2. člen): the bill makes the old 4th paragraph the 5th, lawdiff the 3rd", out)


if __name__ == "__main__":
    unittest.main()
