# Statistics

How to get a figure from a statistics office into the record. Quote the database rather than a press release or an article that reports the figure: the database is tier A and the Auditor can re-run it.

## The data script

Write a short Python script that fetches only the rows your Claim needs, and run it with `evidence.py data`:

```
python3 <skill dir>/scripts/evidence.py data <folder> <script.py>
```

The script follows one contract:

- It starts with a `# /// script` block that pins every dependency to an exact version (`sistat==0.2.0`). `data` refuses a loose pin, because the Audit re-runs the same code.
- Its last line of output is one line of JSON: `{"title": …, "url": …, "rows": [{column: value, …}, …]}`. `url` is the dataset's public page, or the API query URL when there is no page. `title` is the dataset's own title. Write one row per observation, with every column the reader needs to tell rows apart: area, period, unit, and the value.

Name the script after what it fetches (`net-wages-public-sector.py`). `data` keeps a copy in `evidence/files/data/`, runs it with `uv`, and caches the rows next to it, one per line with every column named (`LETO: 2023 | value: 1281.75`). Quote a row with `quote` as you would a paragraph. `verify --live` re-runs the script, so the Audit checks the quote against the database as it is now. `sources` lists the cached rows, so check there first, because another Advocate may already have fetched the table.

Select the rows the Claim compares, and only those. If the Claim says "the highest since 2010", fetch every year since 2010, so the Auditor can see that it is. When a value is provisional or an estimate, the source marks it with a flag column: keep that column in the rows.

## Which source

| Source | What it has | Library |
|---|---|---|
| SURS (SiStat) | Slovenian official statistics: population, wages, prices, pensions, housing, regions, municipalities | `sistat==0.2.0` |
| Eurostat | EU statistics, comparable across member states | `sdmx1==2.28.0`, source `ESTAT` |
| World Bank (World Development Indicators) | About 1,500 indicators for ~217 countries from 1960: GDP, population, poverty, health, energy | `wbgapi==1.0.14` |
| IMF | GDP, inflation, debt, balance of payments, World Economic Outlook forecasts | `imfp==2.1.1`, or `sdmx1`, source `IMF_DATA` |
| UN (UNSD, SDG indicators) | Sustainable Development Goal indicators, national accounts | `sdmx1`, source `UNSD` |
| OECD | Detailed economic and social data, mostly for richer countries | `sdmx1`, source `OECD`, or `opensdmx==0.32.0` |
| ILO | Employment, wages, unemployment | `sdmx1`, source `ILO`, or `ilostat==0.1.1` (new, untested) |
| FAO | Food, agriculture, land use | `faostat==2.0.1` |
| UNESCO / UNICEF | Education / children's health and welfare | `sdmx1`, source `UNESCO` / `UNICEF` |
| Our World in Data | Cleaned data from many sources in one place | `owid-catalog==1.4.1` |

For Slovenia, use SURS. For a comparison across EU countries, use Eurostat, which harmonises the national figures. Use the global sources for countries outside the EU or for series Eurostat does not have. Our World in Data republishes other bodies' data: cite it for a chart-ready series, but name the original producer in the Evidence's `publisher`, and prefer the original when you can reach it. A forecast (IMF World Economic Outlook, for example) is a forecast, not a measurement: say so in the Claim.

The recipes below were run against the live services. For a library without one, read its documentation with `help()` in a short script first.

### SURS: `sistat`

Search and inspect a table first, in a throwaway script (no JSON needed):

```python
import sistat
c = sistat.Client(lang="sl")                    # or "en"; the variable codes stay Slovenian
for t in c.search("povprečne mesečne plače")[:10]:   # accent-insensitive, searched locally
    print(t.id, t.text)
for v in c.metadata("0701001S").variables:
    print(v.code, "|", v.text, "|", v.value_texts[:5], len(v.value_texts))
```

The data script:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["sistat==0.2.0"]
# ///
import json, sistat
c = sistat.Client(lang="sl")
table = "0701001S"
rows = c.get_records(table, {"SEKTOR": "Javni sektor", "LETO": "202*", "PLAČA": "Neto"})
print(json.dumps({"title": c.metadata(table).title,
                  "url": f"https://pxweb.stat.si/SiStatData/pxweb/sl/Data/-/{table}.px",
                  "rows": rows}, ensure_ascii=False))
```

A selection value is a label or a code, a list of them, a glob (`"202*"`, `"*"`), or `"top:5"` for the first five in table order. A variable you leave out comes back with all its values, so select every variable the Claim fixes. Long queries are split and rate-limited for you.

### Eurostat: `sdmx1`

Find the dataset and its dimensions first:

```python
import sdmx
es = sdmx.Client("ESTAT")
flows = sdmx.to_pandas(es.dataflow().dataflow)          # all ~8,000 datasets: id -> title
print(flows[flows.str.contains("minimum wage", case=False)])
msg = es.dataflow("EARN_MW_CUR")
print([d.id for d in msg.structure[0].dimensions])      # the order of the key
for cl_id, cl in msg.codelist.items():
    print(cl_id, list(cl.items)[:10])
```

The data script. Dataset ids are upper case. The key lists one value per dimension, in order, `+` between several values and an empty field for all:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["sdmx1==2.28.0"]
# ///
import json, sdmx
msg = sdmx.Client("ESTAT").data("UNE_RT_A", key="A.Y15-74.PC_ACT.T.SI+AT", params={"startPeriod": "2015"})
rows = sdmx.to_pandas(msg).reset_index().to_dict("records")
print(json.dumps({"title": "Unemployment by sex and age – annual data",
                  "url": "https://ec.europa.eu/eurostat/databrowser/view/une_rt_a/default/table",
                  "rows": rows}, ensure_ascii=False))
```

The same client reaches the other SDMX sources in the table: change `"ESTAT"` to the source id.

### World Bank: `wbgapi`

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["wbgapi==1.0.14"]
# ///
import json, wbgapi as wb
series = "NY.GDP.PCAP.CD"                      # find ids with wb.series.info(q="gdp per capita")
rows = list(wb.data.fetch(series, ["SVN", "AUT", "HRV"], time=range(2015, 2025)))
print(json.dumps({"title": wb.series.get(series)["value"],
                  "url": f"https://data.worldbank.org/indicator/{series}",
                  "rows": rows}, ensure_ascii=False))
```

## Real and nominal amounts

An amount in euros from one year, compared with an amount or a price from another, is nominal unless you adjust it. To state it at another year's prices, fetch a price index as Evidence and adjust it with a calc:

```
calc "<amount>:<value> * <index>:<target period> / <index>:<base period>"
```

1. **Pick the index.** For Slovenia use SURS's consumer price index (CPI). Use Eurostat's harmonised index (HICP, `PRC_HICP_AIND` annual, `PRC_HICP_MIDX` monthly) for a comparison across EU countries. Deflate a spending category with that category's index (food with group 01, food and non-alcoholic beverages), and an income or a total with the all-items index (`SKUPAJ`, `CP00`).
2. **Fetch both periods from one series:** the same index, area, group and base (`2025 = 100`). Index levels on one base divide directly. Don't mix a CPI level with an HICP one, or levels with growth rates.
3. **Match the periods.** An amount for a year goes with that year's annual average. For the current year, when there is no annual average yet, use the latest month, and say so: one month of a food index can sit two points off its neighbours.
4. **Quote the index rows** with `quote`, then write the calc. Its `--method` names the index, the group, the area, the base and both periods, and what the result is: the earlier basket at the later prices, not what the household spends in the later year.

SURS, food and all items, annual average and the months of the current year (both tables on the base 2025 average = 100):

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["sistat==0.2.0"]
# ///
import json, sistat
c = sistat.Client(lang="sl")
table = "0400611S"        # annual; monthly: "0400608S" with "MESEC": "2026M*" and "ŽIVLJENJSKA POTREBŠČINA" for the group
rows = c.get_records(table, {"MERITVE": "Indeks (leto / povprečje leta 2025)",
                             "GLAVNA SKUPINA": ["SKUPAJ", "01 HRANA IN BREZALKOHOLNE PIJAČE"],
                             "LETO": ["2022", "2023", "2024", "2025"]})
print(json.dumps({"title": c.metadata(table).title,
                  "url": f"https://pxweb.stat.si/SiStatData/pxweb/sl/Data/-/{table}.px",
                  "rows": rows}, ensure_ascii=False))
```

Then, with the 2022 food spending of the lowest income quintile (EUR 772.4 million), the 2022 average food index (83.6) and the October 2026 one (102.34):

```
calc "E-CON-D-028:772.4 * E-CON-D-034:102.34 / E-CON-D-033:83.6"      → 945.543 (EUR million, at October 2026 food prices)
```

The base index is often `100`, and that number stands in every row of the base year. Pick the right row with `--at` and the label that sets the row apart (`--at "E-CON-D-033:100=01 HRANA IN BREZALKOHOLNE PIJAČE"`); `--at` takes no `|`, so don't copy the column separator.
