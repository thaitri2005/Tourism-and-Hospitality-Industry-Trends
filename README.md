# Tourism and hospitality industry trends

Research-assistant project for Dr Le Thi Phuong Dung (Jenny), CBM. It collects news, press releases and blog posts
(10 Oct 2016 – 10 Oct 2026) from the nine websites in the brief and answers four questions:

1. the ten key themes in the current industry discussion, and their sentiment;
2. how themes change year by year, and which themes lead each year;
3. the focus of each website's community;
4. key brands (the Global Brands Magazine 2026 top 10 and others) and what they are associated with.

**Read the results in `output/REPORT.pdf`.** Its methodology section (section 2) explains how the data were collected and
analysed; `output/METHODOLOGY_SUMMARY.md` is the same in one paragraph. All tables are in `output/RESULTS.xlsx`.

## Websites

| Website | How it is collected |
|---|---|
| UN Tourism, ETC | live site: sitemaps and news archives |
| WTTC, AHLA, PATA | live site, plus the Wayback Machine for press-release archives that are no longer online (pre-2019/2020) |
| Hospitality Net | live site: random sample of 1,800 article IDs across 2016–2026, plus recent archive pages |
| CTO, Travel Weekly | Wayback Machine copies (both sites answer automated requests with a bot-protection 403); Travel Weekly sampled at up to 170 articles a year |
| IH&RA | no original news in the period; its old “News” page only republished Hospitality Net headlines (documented, not analysed) |

More detail and the reasoning behind each choice: [docs/COLLECTION_NOTES.md](docs/COLLECTION_NOTES.md).

## Running it (Windows / PowerShell, Python 3.12)

```powershell
Set-Location -LiteralPath 'D:\Tourism-and-Hospitality-Industry-Trends'
python run_research.py
```

The launcher creates `.venv`, installs `requirements.txt`, then collects, re-extracts, analyses and writes the report.
It is resumable: after an interruption or Ctrl+C, run **the same command again**; finished work is never repeated.

| Command | Use it to |
|---|---|
| `python run_research.py` | collect anything new or unfinished, then rebuild analysis and report |
| `python run_research.py --collect-only` | only collect (fast to stop and resume) |
| `python run_research.py --offline` | rebuild analysis and report from saved data, no web requests |
| `python run_research.py --report-only` | rebuild `REPORT.html/pdf` from the published tables (seconds) |
| `python run_research.py --sources cto travelweekly` | limit collection to some sites (analysis still uses all data) |
| `python run_research.py --status` | show progress without doing anything |

Exit code `0` = finished; `2` = something needs a rerun later (e.g. a site rate-limited us — rerun after the logged time);
`130` = interrupted; `3` = another run is already active. If a run fails, send `output/diagnostics/latest.zip`.

First run of the analysis downloads the sentiment model (about 500 MB, to `tmp/hf`) and scores roughly 50,000 sentences on
the CPU — expect about an hour. Scores are cached in `data/sentiment_cache.sqlite`, so later runs take minutes.
The report PDF is printed with Microsoft Edge (headless); without Edge, open `output/REPORT.html` and print to PDF.

## Outputs

| Path | Contents |
|---|---|
| `output/REPORT.pdf`, `REPORT.html` | the report for the supervisor |
| `output/METHODOLOGY_SUMMARY.md` | one-paragraph methodology with current numbers |
| `output/RESULTS.xlsx` | every result table, one sheet each, with a README sheet |
| `output/tables/*.csv` | the same tables, plus article-level data (`articles_analysed.csv`, `article_themes.csv`, `article_brands.csv`) |
| `output/figures/*.png` | all charts |
| `output/codebook.json` | the theme, brand and organisation dictionaries and coding rules |
| `output/QUALITY_CHECKS.json` | automated consistency checks of the published analysis |

Article texts stay in `data/corpus.sqlite` (not in git) and are not redistributed.

## Project layout

```text
run_research.py            launcher: environment, locks, logs, diagnostics
research/
  config.py                websites, study window, user agent
  discover.py history.py   sitemap and archive-page discovery (live sites)
  backfill.py              UN Tourism English news archive
  archive.py               Wayback Machine discovery/retrieval and the Hospitality Net ID sample
  http.py robots.py        polite cached HTTP client (3 s spacing, retries, robots rules)
  crawl.py extract.py      download and extract title, date and text
  reextract.py curate.py   re-apply extraction rules to saved raw files; site-specific clean-up
  codebook.py              theme, brand and organisation dictionaries
  sentiment.py             RoBERTa sentence sentiment with a persistent cache
  analyze.py               the four research questions -> tables, figures, workbook
  validation.py            validation sample (draw + score against independent labels)
  report.py                REPORT.html / REPORT.pdf / METHODOLOGY_SUMMARY.md
  run.py runtime.py store.py diagnostics.py   pipeline, logging, database, diagnostics zip
  resources/               VADER lexicon (baseline), validation labels
tests/                     offline tests (no network): python -m pytest -q  (run with .venv\Scripts\python.exe)
```

## Changing the analysis

- Themes, brands and their search terms: `research/codebook.py`. Then `python run_research.py --offline`.
- The report's text is generated from the tables in `research/report.py`; after large data changes, reread the summary
  bullets for sense.
- A new validation sample: `.venv\Scripts\python.exe -m research.validation sample` writes a reading packet to
  `tmp/validation/`; record labels in `research/resources/validation_*.csv`.
