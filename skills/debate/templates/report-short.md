# <The Report's title, word for word>

<Lede: one or two neutral sentences on what the decision is and what this page gives the reader.>

<Meta line: the date of the record and what this page is, e.g. "6 December 2026 · short report on the debate · record as of 23 November 2026".>

<!-- The six "## " sections below, each with its key comment, in this order (Key figures is optional).
     Write the headings and all text in the Report language. The **Labels** stay as written here, or in the
     Report language where report_html.py lists them (Slovenian: Za, Proti, Kaj se spremeni, Ključno dejstvo …).
     Every Evidence link is relative to outputs/, as in the Report: [E-PRO-003](../agent/evidence/E-PRO-003.md).
     Never write which way to decide. Pro and Con get the same space everywhere. -->

## <At a glance> <!-- glance -->

<!-- Exactly four bullets: the four things a reader needs before anything else (what the vote is on, what it costs,
     what the other outcome triggers, who is affected most). Each: a label, a short figure or phrase that reads as a
     headline, then one or two sentences with their Evidence. -->

- **<label>**: <big figure or phrase> — <one or two sentences> [E-…](../agent/evidence/E-….md)

## <Key figures> <!-- figures -->

<!-- Optional. The few figures from figures.json that the whole decision turns on (typically cost), one "### " per
     figure, named by its id, in the order the reader should see them. Under each, the Pro and Con point that the figure bears on, in one or two
     sentences. Mark the bar or point each note argues about with "pins" in figures.json (see the Summariser brief).
     A **Dimension** line attaches that Dimension's "More on this" panel to the end of this section; that Dimension
     then gets no card below. -->

### <figure id>

**Pro**: <one or two sentences>

**Con**: <one or two sentences>

**Dimension**: <a Dimension shown here instead of as a card, or leave the line out>

## <Where each case is stronger> <!-- strength -->

<One sentence: what this section shows.>

**Pro**:

- **<topic>**: <one sentence from Section 3 of the Report, or an Open Question whose status leans Pro>

**Con**:

- **<topic>**: <…>

<Optional: one short paragraph of fine print, such as the Source Tier imbalance from Section 3.>

## <Dimension by Dimension> <!-- dimensions -->

<One sentence: what each card shows.>

### <Dimension name, exactly as the "### " heading in Section 2 of the Report>

**Name**: <optional shorter card title>

**Provisions**: <optional: the articles or sections it covers>

**Group**: <optional: a heading shared by consecutive cards, e.g. "Taxes">

**Scale**: <optional: "<label> <number> · <label> <number> · <unit>", the same unit on every card that has one>

**Changes**: <one or two sentences: what the Motion changes here, from the Report's lead paragraph>

**Figure**: <optional: the id of a figure in figures.json with this Dimension>

**Key fact**: <the one Settled fact that matters most, with its Evidence>

**Pro**: <one or two sentences: Pro's strongest point here>

**Con**: <one or two sentences: Con's strongest point here>

**Key question**: <the Open Question that decides most> · Status: <settled | leaning Pro | leaning Con | unsettled> — <one sentence on why>

**Pro concedes**:

- <each Concession Pro made in this Dimension, one line each; "none" if it made none>

**Con concedes**:

- <…>

**Exchange**:

- **Pro · Opening**: <one or two sentences, about 25–40 words, in the first person plural>
- **Con · Opening**: <…>
- **Pro · Rebuttal**: <…>
- **Con · Rebuttal**: <…>
- **Pro · Rejoinder**: <…>
- **Con · Rejoinder**: <…>

## <Depends on your values> <!-- values -->

<One sentence: what the table shows.>

| <If you weigh more …, Pro is closer> | <Area> | <If you weigh more …, Con is closer> |
|---|---|---|
| <the priority that favours Pro> | <area> | <the priority that favours Con> |

## <What we don't know> <!-- unknowns -->

<One sentence: what this list is.>

1. **<the missing piece>**: <what it would settle>
