# Research papers

How to bring a research finding into the record: what a policy does in practice, what a study measured, what a field has concluded. Quote the paper itself, rather than an article or a press release about it.

## Find

```
python3 <skill dir>/scripts/evidence.py papers <words …> [--since YEAR] [--reviews] [--open] [--max N]
python3 <skill dir>/scripts/evidence.py papers <DOI>          # one paper: type, retraction, authors, funders, copies, abstract
```

`papers` searches OpenAlex, an open index of scholarly works. Each hit shows its year, type, citation count, venue and DOI, and whether a free copy exists. Write the search words in English, the language most research is indexed in. Add the country's name when the setting matters (`minimum wage employment Slovenia`). WebSearch and Google Scholar find papers too: look each one up with `papers <DOI>` before you cite it.

Look for the strongest kind of evidence first:

1. A **systematic review or meta-analysis** pools many studies, so one cherry-picked study can't outweigh it. Use `--reviews`.
2. A **peer-reviewed study** in a journal.
3. A **preprint or working paper** (type `preprint`, from arXiv, SSRN, NBER, RePEc and the like) has not been peer-reviewed yet. Cite it when it is the newest or the only work on the question, and say in the Claim that it is a preprint.

A study measures one setting: a country, a period, a population. When you apply it to the Motion's setting, say so in the Claim, and prefer studies from the Motion's country or from comparable ones. Citation counts show attention, not correctness, and new work has had no time to gather them.

## Check before you cite

Run `papers <DOI>` on every paper you cite. It shows:

- **RETRACTED** when the paper has been withdrawn. A retracted paper shows only what its authors once claimed, so find another source.
- the **type**: `review`, `article`, `preprint` and others. A preprint whose published version exists has both listed as copies: cite the published one.
- the **funders**, where OpenAlex records them. Otherwise read the paper's acknowledgements and conflict-of-interest statement, and put what you find on the `Advocate's note:` line. An industry, party or campaign funder makes the paper tier C.

## Quote the full text

Quote the results or the conclusions in the full text, not the abstract. Abstracts compress and often overstate. Quote the abstract only when no full text can be reached, and say so on the `Advocate's note:` line.

`papers <DOI>` lists every copy, with its version: `publishedVersion` is the journal's, `acceptedVersion` is the peer-reviewed manuscript and `submittedVersion` is the preprint. Quote the published or accepted version where you can. If only the submitted version is open, quote it and note the version, because its text can differ from the published paper.

To open a copy:

- `fetch` the open PDF link. When the publisher's PDF refuses (HTTP 403) or returns no text, `fetch` the article's HTML page (the DOI link, or `…/html`) with `--render`, which often has the full text.
- Repository copies (arXiv, SSRN, university repositories, Europe PMC for medicine and life sciences) usually fetch without trouble.
- If every copy is paywalled, raise an Evidence Request for the paper by DOI. The user may have access through a library.

The Evidence's `published` is the paper's publication date, `author` is its authors (first three, then "et al."), and `publisher` is the journal, or the repository for a preprint.
