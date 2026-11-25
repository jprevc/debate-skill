# Site recipes

URL schemes that reach a document directly, so you don't spend turns finding your way through a site. All tested with `scripts/evidence.py fetch`. `--render` marks the sites that need JavaScript.

## Slovenia

| What | Recipe |
|---|---|
| Consolidated law, all versions (PIS) | `https://pisrs.si/pregledPredpisa?id=<ZAKO…>` with `--render`. The rendered page lists HTML/Word/PDF download links of the consolidated text. |
| Uradni list issue (PDF) | `https://pisrs.si/api/uradni-list/objava/<file>.pdf`. No rendering needed, and no certificate trouble, unlike uradni-list.si. |
| Bill file in the National Assembly (DZ) | `https://www.dz-rs.si/wps/PA_DZ-LN-Iskalnik/EpaLinkServlet?epa=<EPA, e.g. 15-X>&pathPrefix=/wps/portal` with `--render`. Lists every document in the bill's file: proposal, Government opinion, Legislative and Legal Service opinions, opinions of others, amendments. Fetch a listed `…izbran?uid=…&tip=doc` link with `--render`. Its attachment link (`imss.dz-rs.si/IMiS/…`) is the PDF: fetch that one without `--render`. |
| Constitutional Court decision | `https://www.us-rs.si/sl/zadeve-in-odlocitve/odlocitve/<case lowercase, no slash: u-i-10626>` with `--render`. The page has the full text, and links to the decision and each separate opinion as PDFs. The site's search form doesn't work through a URL. |
| Case law (Supreme and higher courts) | `https://www.sodnapraksa.si/?q=<terms>&_submit=išči` with `--render` lists the results. |
| Official statistics (SURS, SiStat) | A `data` script with `sistat`: `reference/statistics.md`. The table's human-readable page is `https://pxweb.stat.si/SiStatData/pxweb/sl/Data/-/<id>.px`. |
| Fiscal Council | The domain is `fs-rs.si`, not `fiskalni-svet.si`. Analyses are PDFs under `https://www.fs-rs.si/wp-content/uploads/…`. |

## EU

EUR-Lex answers a plain fetch with an empty page, so every EUR-Lex row needs `--render`. `<LANG>` is the two-letter language code in capitals: `SL`, `EN`, `DE`. Each rendered page lists a "Download notice" link: that is metadata, not the text, so don't fetch it.

| What | Recipe |
|---|---|
| Finding a CELEX number | Build it from the act's or case's number. Directive 2006/112/EC is `32006L0112`: `3`, the year, `L` for a directive (`R` regulation, `D` decision), the number padded to four digits. Case C-390/15 is `62015CJ0390`: `6`, the year, `CJ` for a Court of Justice judgment (`CC` an Advocate General's opinion, `CO` an order; `TJ` a General Court judgment), the case number padded to four digits. From a common name only ("the VAT Directive"), WebSearch it with "EUR-Lex" to get the number. For a case, `https://curia.europa.eu/juris/liste.jsf?num=<C-390/15>&language=<lang>` with `--render` lists its judgment, opinion and ECLI. |
| EU act, as published | `https://eur-lex.europa.eu/legal-content/<LANG>/TXT/?uri=CELEX:<celex, e.g. 32006L0112>` with `--render`. Full text, one paragraph per line. This is the text as adopted, without later amendments. The page names the current consolidated version: fetch with the keyword `Current consolidated version`, and its date is on the next line. |
| EU act, consolidated (as amended) | `https://eur-lex.europa.eu/legal-content/<LANG>/TXT/?uri=CELEX:0<celex without its leading 3>-<YYYYMMDD>`, e.g. `CELEX:02006L0112-20250414`, with `--render`. Use this for the law in force. For an earlier version, `https://eur-lex.europa.eu/legal-content/<LANG>/ALL/?uri=CELEX:<celex>` with `--render` links every consolidated version. Only 25 links are shown, not in date order, and some may not be in force yet: add a date (`20220701`) as a keyword to list just that one. The links point to the English `AUTO` page: change `EN/AUTO` to `<LANG>/TXT`. |
| CJEU judgment or Advocate General's opinion | `https://eur-lex.europa.eu/legal-content/<LANG>/TXT/?uri=CELEX:<celex, e.g. 62015CJ0390>` with `--render`, or by ECLI: `…/TXT/?uri=ecli:<ECLI:EU:C:2017:174>`. Full text in every EU language. Each paragraph number sits on its own line just above its paragraph, with a line holding only a pipe on each side. The operative part follows the keyword for "On those grounds" in the page's language (`Iz teh razlogov`). Use EUR-Lex, not curia.europa.eu: curia's document pages are reached only through JavaScript links that `fetch` doesn't list. |
