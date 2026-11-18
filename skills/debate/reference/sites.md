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
| Official statistics (SURS, SiStat) | `evidence.py pxweb` (the default database). Search with a trailing `*` to match word stems (`pokojnin*`, `najemnin*`). Use `pxweb meta` for value codes, and `top:N` for the latest N periods. The table's human-readable page is `https://pxweb.stat.si/SiStatData/pxweb/sl/Data/-/<id>.px`. |
| Fiscal Council | The domain is `fs-rs.si`, not `fiskalni-svet.si`. Analyses are PDFs under `https://www.fs-rs.si/wp-content/uploads/…`. |
