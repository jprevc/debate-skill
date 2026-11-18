# Evidence, Claims and Evidence Requests

The rules every participant in a debate shares. The participants are the main agent, the Advocates, the Auditors and the Judge. Terms follow the skill's glossary.

## Evidence

One piece of Evidence is one file: `evidence/<ID>.md`. An ID is permanent once it has been assigned.

Sources go through `scripts/evidence.py` (in the skill dir; run it with `-h` for options):

```
python3 <skill dir>/scripts/evidence.py sources <folder> <keyword> [keyword …]        # sources already cached by anyone in this debate
python3 <skill dir>/scripts/evidence.py fetch  <folder> <url> <keyword> [keyword …]   # cache page/PDF as text, print matching paragraphs
        [--render]                                                                     # load it in headless Chromium first (JavaScript sites)
python3 <skill dir>/scripts/evidence.py pxweb search <word*> [word* …]                # statistical tables (SiStat by default; --base for another PxWeb API)
python3 <skill dir>/scripts/evidence.py pxweb meta <table> [CODE [keyword]]           # a table's variables and value codes
python3 <skill dir>/scripts/evidence.py pxweb fetch <table> CODE=v1,v2 CODE=top:N … --folder <folder>   # cache the selected rows as text
python3 <skill dir>/scripts/evidence.py search <cached file> <keyword> [keyword …]     # more keyword hits in a cached file
python3 <skill dir>/scripts/evidence.py show   <cached file> <A-B>                     # read paragraphs A-B (max 40)
python3 <skill dir>/scripts/evidence.py quote  <folder> <cached file> <A-B> --id … --added-by … --stage … \
        --title … --publisher … --language … [--author …] [--published …] [--from TEXT] [--to TEXT] [--translation TEXT]
```

`fetch` stores a text copy in `evidence/files/web/` with one paragraph per line, so ranges are paragraph numbers. The cache is shared: what any participant fetched, every other participant can reuse with `sources` and `search`, at no download cost. When a plain `fetch` returns little or no text, the site needs JavaScript: rerun it with `--render`. A rendered page also lists its document links (PDF, attachments). `fetch` the one you need, because the document itself is the better source. Known URL schemes for particular sites are in `reference/sites.md`. For official statistics, query the statistical office's database with `pxweb` rather than quoting a press release about it. `pxweb fetch` caches one row per line with every column named (`LETO: 2025`), so `quote` and the Audit work on a row exactly as on a paragraph. Select only the rows your Claim needs. `quote` copies the quote and one paragraph of context on each side straight from that copy into the Evidence file, and records `source_file` and `source_lines`. Use `--from` and `--to` to trim the quote to a sentence within its first and last paragraph. That keeps every quote verbatim by construction, and lets the Audit check it mechanically. `templates/evidence.md` shows the result. Write an Evidence file by hand only for a source the script can't fetch but you could read, and then fill in every field of the template.

| Prefix | Added by |
|---|---|
| `E-PRIMARY-NNN` | main agent: the Primary Text |
| `E-PRO-NNN`, `E-CON-NNN` | the Pro or Con Advocate |
| `E-PRO-A-NNN`, `E-CON-B-NNN` | an Advocate assigned to group A, B, … |
| `E-USER-NNN` | the user, in answer to an Evidence Request; files go in `evidence/files/` |

To add Evidence, take the highest existing number for your prefix in `evidence/` and add one. Numbers are zero-padded to three digits.

Rules:

- **Verbatim.** The quote is copied exactly from the source, in the source's original language, which is what `quote` does. If that language differs from the Report language, pass `--translation` into the Report language. The context holds a paragraph before and after the quote, so the Auditor can check whether it was cherry-picked.
- **Opened.** Every piece of Evidence comes from a source fetched during this debate. If `fetch` fails or returns a paywall, consent page or empty text, try another copy of the same document (official site, archive.org, a PDF link). Failing that, raise an Evidence Request. Knowledge from memory stays out of the record.
- **Cited.** Every piece of Evidence is cited by at least one Claim. Record only what an argument uses. There is no cap on how much Evidence there is.
- **Own files only.** An Advocate creates and edits only the Evidence files with its own prefix. To use the other Side's Evidence, cite its ID. Which Claims cite which Evidence is worked out from the case files and indexed in `ledger.md`, so Evidence files don't record that.
- **Remarks go in Context.** The `## Audit` section belongs to the Auditor, so leave it as `quote` writes it. Put your own remarks about a source, such as who funds it or a caveat, on an `Advocate's note:` line at the end of `## Context`.
- Sources may be in any language.

## Source Tiers

The Auditor grades every source by its independence from the outcome of the Motion. `motion.md` gives examples of each tier for this debate's domain.

- **A**: primary or authoritative. The Primary Text, official statistics, court rulings, peer-reviewed research.
- **B**: independent experts, such as fiscal councils, courts of audit, international bodies and quality journalism.
- **C**: interested parties, such as advocacy groups, think tanks, parties, campaigns, vendors and the user's own situation. Record who funds or runs the source.
- **D**: opinion, such as op-eds, blogs and social media. Valid only as Evidence of what someone said, never as Evidence of a fact.

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
| **Inference** | cites the Evidence it builds on and shows the reasoning step |

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
