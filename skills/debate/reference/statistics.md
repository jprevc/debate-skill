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
