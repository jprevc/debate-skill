# Evidence, Claims and Evidence Requests

The rules every participant in a debate shares. The participants are the main agent, the Advocates, the Auditors and the Judge. Capitalised terms (Motion, Side, Claim, Evidence, Dimension …) mean what SKILL.md and this file define.

## Evidence

One piece of Evidence is one file: `evidence/<ID>.md`. An ID is permanent once it has been assigned.

Sources go through `scripts/evidence.py` (in the skill dir; run it with `-h` for options):

```
python3 <skill dir>/scripts/evidence.py sources <folder> <keyword> [keyword …]        # sources already cached by anyone in this debate
python3 <skill dir>/scripts/evidence.py fetch  <folder> <url> <keyword> [keyword …]   # cache page/PDF as text, print matching paragraphs
        [--render]                                                                     # load it in headless Chromium first (JavaScript sites)
        [--archive]                                                                    # the latest Wayback Machine snapshot instead (site down)
python3 <skill dir>/scripts/evidence.py pxweb search <word*> [word* …]                # another PxWeb database (--base); for SiStat use a data script
python3 <skill dir>/scripts/evidence.py pxweb meta <table> [CODE [keyword]]           # a table's variables and value codes
python3 <skill dir>/scripts/evidence.py pxweb fetch <table> CODE=v1,v2 CODE=top:N … --folder <folder>   # cache the selected rows as text
python3 <skill dir>/scripts/evidence.py papers <words …> | <DOI>                     # research papers in OpenAlex; one paper's type, retraction, funders (reference/research.md)
python3 <skill dir>/scripts/evidence.py data <folder> <script.py>                     # run a pinned statistics script, cache its rows as text (reference/statistics.md)
python3 <skill dir>/scripts/evidence.py search <cached file> <keyword> [keyword …]     # more keyword hits in a cached file
python3 <skill dir>/scripts/evidence.py show   <cached file> <A-B>                     # read paragraphs A-B (max 40)
python3 <skill dir>/scripts/evidence.py quote  <folder> <cached file> <A-B> --id … --added-by … --stage … \
        --title … --publisher … --language … [--author …] [--published …] [--from TEXT] [--to TEXT] [--translation TEXT]
python3 <skill dir>/scripts/evidence.py calc   <folder> "<formula>" --id … --added-by … --stage … --title … --method …
```

The user's own files stay unchanged in `../sources/`; their text is in `evidence/files/user-*.txt` (made by `evidence.py import`, which records the original as the url). Quote from those extracts like any cached file. `fetch` stores a text copy in `evidence/files/web/` with one paragraph per line, so ranges are paragraph numbers. The cache is shared: what any participant fetched, every other participant can reuse with `sources` and `search`, at no download cost. When a plain `fetch` returns little or no text, the site needs JavaScript: rerun it with `--render`. A rendered page also lists its document links (PDF, attachments). `fetch` the one you need, because the document itself is the better source. Known URL schemes for particular sites are in `reference/sites.md`. For a statistical figure, query the database with a `data` script, as `reference/statistics.md` describes, rather than quoting a press release about it. `data` caches one row per line with every column named (`LETO: 2025`), so `quote` and the Audit work on a row exactly as on a paragraph. `quote` copies the quote and one paragraph of context on each side straight from that copy into the Evidence file, and records `source_file` and `source_lines`. Use `--from` and `--to` to trim the quote to a sentence within its first and last paragraph. That keeps every quote verbatim by construction, and lets the Audit check it mechanically. `templates/evidence.md` shows the result. Write an Evidence file by hand only for a source the script can't fetch but you could read, and then fill in every field of the template.

When a site is down, `fetch --archive` caches the latest Wayback Machine snapshot of the page instead (`…-archived.txt`). Its Evidence keeps the page's own `url` and adds `archive_url:`, the snapshot quoted. With `EVIDENCE_ARCHIVE=1` set, `quote` also asks the Wayback Machine to snapshot each web page it quotes from, once per page, and records it as `archive_url:`, which the HTML Report links. The setting is off by default, because it sends every quoted URL to archive.org. A snapshot that fails (Save Page Now is rate-limited) doesn't fail the quote: `evidence.py archive <folder>` retries every quoted page that has none yet.

| Prefix | Added by |
|---|---|
| `E-PRIMARY-NNN` | main agent: the Primary Text |
| `E-PRO-NNN`, `E-CON-NNN` | the Pro or Con Advocate |
| `E-PRO-A-NNN`, `E-CON-B-NNN` | an Advocate assigned to group A, B, … |
| `E-USER-NNN` | the user, in answer to an Evidence Request; the file goes in `../sources/` and its text is imported into `evidence/files/user-*.txt` |

To add Evidence, take the highest existing number for your prefix in `evidence/` and add one. Numbers are zero-padded to three digits.

Rules:

- **Verbatim.** The quote is copied exactly from the source, in the source's original language, which is what `quote` does. If that language differs from the Report language, pass `--translation` into the Report language. The context holds a paragraph before and after the quote, so the Auditor can check whether it was cherry-picked.
- **Opened.** Every piece of Evidence comes from a source fetched during this debate. If `fetch` fails or returns a paywall, consent page or empty text, try another copy of the same document (official site, `fetch --archive`, a PDF link). Failing that, raise an Evidence Request. Knowledge from memory stays out of the record.
- **Cited.** Every piece of Evidence is cited by at least one Claim. Record only what an argument uses. There is no cap on how much Evidence there is.
- **Own files only.** An Advocate creates and edits only the Evidence files with its own prefix. To use the other Side's Evidence, cite its ID. Which Claims cite which Evidence is worked out from the case files and indexed in `ledger.md`, so Evidence files don't record that.
- **Remarks go in Context.** The `## Audit` section belongs to the Auditor, so leave it as `quote` writes it. Put your own remarks about a source, such as who funds it or a caveat, on an `Advocate's note:` line at the end of `## Context`.
- Sources may be in any language.

### Calculations

A number you work out yourself, such as a sum, a share of GDP, a ratio or a gross amount from a net one, is a **calc**: Evidence that `evidence.py calc` writes from numbers already quoted in other Evidence. Cite the calc wherever you state its result, the same way you cite a quote.

```
python3 <skill dir>/scripts/evidence.py calc <folder> "E-CON-B-040:5159.12 / (1 - E-PRO-B-046:36.83 / 100)" \
        --id E-PRO-B-051 --added-by PRO-B --stage rebuttal --title "Gross wage at which the cap starts, EUR a month" \
        --method "The highest pension base (E-CON-B-040) is net; dividing by one minus the average rate of tax and contributions (E-PRO-B-046) gives the gross wage."
```

- Write each input as `<Evidence ID>:<number>`, copied from that Evidence's Quote or Context as a plain decimal: `36,83 %` is `36.83`, `1.195 mio EUR` is `1195`. Any other number in the formula is a constant (`100`, `12` months). Formulas use `+ - * / **` and brackets.
- `calc` refuses an input that is not in its Evidence, an input that failed the Audit, and anything that is not arithmetic. It writes the formula and its result as the Quote, and each input with the passage it stands in.
- `--method` says what each input is and why the formula combines them that way: the same year, unit and population, or how they differ. The Auditor checks exactly that.
- A Claim that rests on a calc is an Inference: cite the calc, and the Evidence of the inputs where the Claim uses their meaning.

The Report is checked the same way: `report_html.py` prints a `NUMBER` line for every number in a sentence that none of the sentence's Evidence states, even rounded, and a `FIGURE` line for every value in `figures.json` that none of its Evidence states. A number you computed without a calc ends up as one of those lines.

## Source Tiers

The Auditor grades every source by its independence from the outcome of the Motion. `motion.md` gives examples of each tier for this debate's domain.

- **A**: primary or authoritative. The Primary Text, official statistics, court rulings, peer-reviewed research.
- **B**: independent experts, such as fiscal councils, courts of audit, international bodies and quality journalism. Also research not yet peer-reviewed: preprints and working papers by independent researchers.
- **C**: interested parties, such as advocacy groups, think tanks, parties, campaigns, vendors and the user's own situation. Record who funds or runs the source.
- **D**: opinion, such as op-eds, blogs and social media, and retracted papers. Valid only as Evidence of what someone said, never as Evidence of a fact.

## Claims

A Claim is one assertion. It is written in a case file using this format:

```
**PRO-7** · Dimension: <name> · Type: Factual · Evidence: E-PRO-003, E-PRIMARY-001
<the assertion, one to three sentences>
```

The header line holds only these fields. A Value Claim leaves out `· Evidence: …` entirely. Pinpoints such as an article or page number go in the assertion, not after an Evidence ID.

Claim IDs are `PRO-N` and `CON-N`, or `PRO-A-N` when the Advocate is in a group. Numbering continues across Stages: to add a Claim, take the highest number used in your Side's earlier case files and add one.

| Type | What it needs |
|---|---|
| **Factual** | cites Evidence |
| **Predictive** ("this will cause Y") | cites Evidence for the mechanism, or for comparable cases elsewhere |
| **Value** ("fairness requires…") | no Evidence; the label is what makes it honest |
| **Inference** | cites the Evidence it builds on and shows the reasoning step; a number it computes cites a calc (see Calculations) |

A Claim that depends on an open Evidence Request gets the marker `· Pending Evidence: R-PRO-2` after its Evidence list. Write a Claim with no support as a Value or Inference Claim, which tells the reader exactly how much weight it carries.

## Responses (Rebuttal and Rejoinder)

Every opposing Claim gets exactly one response:

```
**Re CON-4** · Rebut · Evidence: E-PRO-011
<counter-Evidence, or the flaw in CON-4's Evidence>
```

The header line holds only these fields. Don't restate the opposing Claim or your own position in it, as in `**Re CON-4** · Rebut (Pro: X)`; `ledger.py` rejects that header. Put it in the text below.

- **Rebut**: counter-Evidence, or a flaw shown in the opposing Evidence.
- **Mitigate**: accept the Claim but argue it matters less than claimed, with reasoning or Evidence.
- **Concede**: state plainly that you have no counter. A Concession is a sign of a credible Advocate, and the Judge treats conceded Claims as settled.

## Evidence Requests

Raise one when Evidence that matters to your argument can only be obtained by the user. Write it in the `## Evidence Requests` section of your case file:

```
**R-PRO-2** · Priority: critical · For: PRO-7, PRO-9
Needed: <exactly what document, figure or fact>
Why I can't get it: <paywall / not public / user's private situation / …>
Tried: <every URL you tried, each with what failed: certificate, DNS, timeout, JavaScript, 403, paywall, not on the page>
Where the user could get it: <the most direct URL you know; failing that, the site plus the exact path, document number, date or search terms that find it>
Effort: <browser (minutes) | account or paywall | freedom-of-information request (weeks) | ask a person>
```

- `Where` is what the user acts on. Name the document precisely enough that they can find it without searching: its number (EPA, case number, gazette issue), its date and its title.
- Use priority `critical` when a Claim stands or falls on the request, and `nice-to-have` when the request only strengthens a Claim.
- Number requests with your own prefix (`R-PRO-N`, `R-CON-A-N`), continuing across Stages.
