# Tourism and hospitality discourse: preliminary collection and analysis

Snapshot: 2026-10-11T07:25:11.984861+00:00. Requested window: 2016-10-10 through 2026-10-10. English only.

**This is an incomplete, exploratory corpus, not a completed nine-source industry study.** Counts below describe successfully collected eligible records. Unavailable sources are not zero-discussion sources.

Collected 2,886 documents; 2,494 pass date/language/length checks. The primary analysis uses 2,224 news/blog article occurrences after within-source/year deduplication; 257 report summaries/PDF records are kept separately. Current-window articles: 169.

## Source coverage

| source | access_status | extracted | core_unique_occurrences | report_records | remaining |
| --- | --- | --- | --- | --- | --- |
| untourism | public_research_review | 1486 | 1305 | 0 | 0 |
| wttc | public_research_review | 780 | 659 | 0 | 0 |
| ihra | source_verification_required | 0 | 0 | 0 | 0 |
| pata | publisher_authorization_required | 0 | 0 | 0 | 0 |
| ahla | publisher_authorization_required | 0 | 0 | 0 | 0 |
| etc | public_research_review | 620 | 260 | 257 | 0 |
| cto | public_research_review | 0 | 0 | 0 | 0 |
| hospitalitynet | publisher_authorization_required | 0 | 0 | 0 | 0 |
| travelweekly | publisher_authorization_required | 0 | 0 | 0 | 0 |

![Coverage](figures/coverage.png)

## Ten leading current candidate themes
These are ranked mentions of a predefined 14-concept codebook, not ten independently validated discoveries. One article can match multiple concepts. Equal-source shares prevent the largest collected source from dominating; this does not repair missing sources. Current window: 11 October 2025 through 10 October 2026.

| theme | articles | article_share_pct | equal_source_share_pct | sources_mentioning |
| --- | --- | --- | --- | --- |
| Sustainability, climate and nature | 112 | 66.3 | 69.4 | 3 |
| Health, safety and crisis resilience | 103 | 61.0 | 63.4 | 3 |
| Transport and connectivity | 88 | 52.1 | 51.0 | 3 |
| Culture, heritage and experiences | 73 | 43.2 | 50.6 | 3 |
| Partnerships, governance and institutions | 88 | 52.1 | 49.6 | 3 |
| Demand, performance and recovery | 87 | 51.5 | 44.3 | 3 |
| Investment, infrastructure and development | 89 | 52.7 | 43.8 | 3 |
| Inclusion, accessibility and communities | 65 | 38.5 | 42.1 | 3 |
| Workforce, skills and education | 88 | 52.1 | 41.6 | 3 |
| Policy, visas and travel facilitation | 51 | 30.2 | 30.6 | 3 |

## Themes by year and website
The CSV `themes_by_source_year.csv` includes numerator, denominator, small-sample flags, and partial-year flags. Compare years within sources first. The available sources and archive depth differ. No industry-wide historical trend is claimed.


![Source themes](figures/themes_by_source.png)

![Annual themes untourism](figures/themes_over_time_untourism.png)

![Annual themes etc](figures/themes_over_time_etc.png)

![Annual themes wttc](figures/themes_over_time_wttc.png)

## Brands and organizations
Dictionary-based name-family matches are exploratory and non-exhaustive. Corporate ownership and formal partnerships are not inferred. Brand-topic associations use a local 350-character context and need semantic review.

| entity | documents | sources |
| --- | --- | --- |
| Amadeus | 45 | 2 |
| Hilton | 43 | 3 |
| Expedia | 34 | 3 |
| Trip.com | 34 | 3 |
| Radisson | 31 | 2 |
| TUI | 29 | 2 |
| Intrepid | 26 | 2 |
| Accor | 26 | 2 |
| Abercrombie & Kent | 26 | 1 |
| Iberostar | 26 | 2 |
| Carnival | 25 | 1 |
| Marriott | 23 | 2 |
| IHG | 20 | 3 |
| Airbnb | 20 | 3 |
| Tripadvisor | 16 | 2 |

## Independent topic discovery
TF-IDF/NMF provides a separate discovery check. Terms below require human labeling; geographic clusters and communication formats can appear alongside substantive themes. Model status: exploratory_unreviewed. A skipped model has no inferred topic results.

| cluster | documents_dominant | top_terms |
| --- | --- | --- |
| 1 | 301 | development; sustainable; sustainable development; silk; silk road; road; rifai; international; international year; organization; taleb rifai; taleb |
| 2 | 75 | visitor spending; spending; visitor; international visitor; domestic; reach; domestic visitor; research; impact research; expected; projected; jobs |
| 3 | 93 | respondents; sentiment; europeans; travellers; trip; europe; long-haul; trips; planning; months; summer; survey |
| 4 | 277 | uk; covid-; health; safe; jobs; protocols; measures; testing; travellers; guevara; gloria guevara; gloria |
| 5 | 143 | arrivals; demand; europe; tourist arrivals; destinations; international tourist; growth; compared; tourist; performance; markets; recorded |
| 6 | 46 | awards; sustainable cultural; cultural; heritage; ectn; europa nostra; nostra; winners; europa; cultural heritage; prize; cultural routes |
| 7 | 148 | summit; global summit; global; leaders; ceo; future; president ceo; growth; president; event; influential; leadership |
| 8 | 59 | contribution gdp; gdp; million jobs; contribution; million; jobs; billion; economy; nearly; reach; levels; employment |
| 9 | 377 | sustainability; sustainable; action; climate; report; change; businesses; hospitality; global; support; hotels; climate action |
| 10 | 458 | pololikashvili; secretary-general; education; innovation; investments; zurab; zurab pololikashvili; investment; development; secretary-general zurab; regional; africa |
| 11 | 56 | scth; course; executive training; training course; training; themis foundation; themis; saudi; dr; executive; saudi arabia; arabia |
| 12 | 15 | emissions; gas emissions; greenhouse gas; gas; greenhouse; intensity; global center; saudi-based sustainable; saudi-based; emissions intensity; sustainable global; footprint |
| 13 | 99 | villages; rural; best villages; rural development; best; upgrade programme; upgrade; applications; rural destinations; gastronomy; network; programme |
| 14 | 58 | eu; manifesto; manifesto alliance; alliance; europe; member states; certificate; restrictions; organisations; member; states; tourismmanifesto eu |
| 15 | 19 | gdp contribution; forecasting; reach; jobs lost; visitor spend; lost pandemic; jobs year; peak; jobs; lost; set contribute; peak forecasts |

## Sentiment
`sentiment_unvalidated.csv` and its summary are an optional TextBlob lexicon baseline on theme-related contexts. They have not been validated on this domain and must not be reported as reliable industry attitudes. Mixed positive/negative contexts are retained. Publisher promotional tone and incomplete coverage remain major limitations.

## What remains
Publisher authorization/export arrangements for PATA, AHLA, Hospitality Net, and Travel Weekly; verification of the IH&RA source; CTO access; full report access where downloads are gated; reconciliation of discovery coverage; broader manual extraction/date review; a held-out human-coded validation set; theme-codebook revision; and semantic review of brand associations.

## Reproducibility and retention
Source URLs, dates, extraction flags, exclusions, duplicate pairs, codebook, and model settings are exported under `tables/`. Full text remains in the local SQLite database and permitted raw cache, outside the shareable report. No messages were sent and no download forms were submitted. Each publisher retains its content rights.