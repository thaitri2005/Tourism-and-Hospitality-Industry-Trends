# Audited exploratory findings

Analysis run: `20261012T102131Z-d0e08056`. Automated audit: **completed_with_limitations**.

The automated workflow reviewed all **5,659 saved documents**, including exclusions, and all **20,524 theme assignments**, **6,006 entity rows**, **3,941 brand/theme rows**, **20,524 sentiment rows**, and **15 NMF clusters**. No manual annotation step is pending.

The research sample contains **4,829 core article occurrences**, **257 supplementary report records**, and **1124 current-window articles**. Dates: 2016-10-10 through 2026-10-10; current: 2025-10-11 through 2026-10-10. These are collected publisher discussions, not a complete industry census.

## Source coverage

| Source | Saved | Core articles | Current | Observed years |
| --- | --- | --- | --- | --- |
| UN Tourism | 1486 | 1305 | 41 | 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026 |
| WTTC | 780 | 659 | 99 | 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026 |
| IH&RA | 46 | 0 | 0 | None |
| PATA | 1830 | 1731 | 307 | 2017, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026 |
| AHLA | 301 | 286 | 60 | 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026 |
| European Travel Commission | 620 | 260 | 29 | 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026 |
| Caribbean Tourism Organization | 0 | 0 | 0 | None |
| Hospitality Net | 596 | 588 | 588 | 2026 |
| Travel Weekly | 0 | 0 | 0 | None |

CTO and Travel Weekly remain held after HTTP 403 responses. IH&RA records have no eligible core articles. Hospitality Net has only a very small recent sample. Missing years mean no collected observations, not no discussion. Supplementary reports are excluded from the core article denominators.

## Ten current themes with stronger focus evidence

This sensitivity view uses **equal_source_min20** and ranks the mean within-source percentage of articles meeting the disclosed focus rule. With the minimum-20 scenario, sources with fewer than 20 current articles are excluded only from this comparison. The complete original mention ranking remains available in `../tables/current_theme_ranking.csv`. The focus rule is a heuristic, not a calibrated topic classifier. Percentages are multi-label and need not total 100%.

| Theme | Focus % | Any mention % | All-source mention rank | Article-weighted mention rank |
| --- | --- | --- | --- | --- |
| Workforce, skills and education | 21.6 | 50.3 | 1 | 1 |
| Demand, performance and recovery | 21.3 | 42.2 | 4 | 4 |
| Sustainability, climate and nature | 20.6 | 47.7 | 2 | 7 |
| Culture, heritage and experiences | 16.2 | 42.1 | 5 | 2 |
| Health, safety and crisis resilience | 14.9 | 43.5 | 3 | 10 |
| Transport and connectivity | 12.8 | 40.9 | 6 | 5 |
| Investment, infrastructure and development | 10.3 | 37.3 | 7 | 3 |
| AI and digital technology | 9.9 | 21.1 | 12 | 6 |
| Inclusion, accessibility and communities | 7.2 | 34.2 | 8 | 9 |
| Partnerships, governance and institutions | 7.1 | 31.0 | 9 | 11 |

Across the full corpus, **7,073 / 20,524** assignments have stronger focus evidence; **13,451** are incidental or uncertain under this rule. Do not describe every keyword match as a main topic. All weighting and leave-one-source-out results are in `current_rank_sensitivity.csv` and `current_focus_rank_sensitivity.csv`.

## Website focus across the collected period

| Source | Articles | Three leading focus themes |
| --- | --- | --- |
| ahla | 286 | Workforce, skills and education (53.1%); Distribution, booking and business models (9.1%); Policy, visas and travel facilitation (7.7%) |
| etc | 260 | Health, safety and crisis resilience (42.3%); Demand, performance and recovery (31.9%); Sustainability, climate and nature (25.8%) |
| hospitalitynet | 588 | AI and digital technology (29.9%); Workforce, skills and education (23.0%); Investment, infrastructure and development (13.1%) |
| pata | 1731 | Health, safety and crisis resilience (23.2%); Sustainability, climate and nature (22.6%); Transport and connectivity (22.0%) |
| untourism | 1305 | Sustainability, climate and nature (37.8%); Health, safety and crisis resilience (21.8%); Workforce, skills and education (20.4%) |
| wttc | 659 | Health, safety and crisis resilience (42.3%); Workforce, skills and education (38.2%); Demand, performance and recovery (34.6%) |

Each row uses that website's observed period, which differs across publishers. This is a description of collected coverage, not a like-for-like census comparison.

## Historical discussion in a fixed-source panel

The following panel uses only UN Tourism and ETC in years when both have observations. This holds publisher identity constant; changes in publication selection and small annual samples remain limitations. Both endpoint years are partial. Full per-website/year results are in `topic_focus_by_source_year.csv` and `../tables/themes_by_source_year.csv`.

| Year | Article counts (UN / ETC) | Leading focus themes (equal source weighting) | Caution |
| --- | --- | --- | --- |
| 2016 | 63 / 4 | Health, safety and crisis resilience (29.8%); Demand, performance and recovery (14.9%); Sustainability, climate and nature (13.5%) | partial year |
| 2017 | 190 / 16 | Sustainability, climate and nature (23.9%); Culture, heritage and experiences (13.9%); Demand, performance and recovery (13.3%) | small source cell |
| 2018 | 158 / 15 | Demand, performance and recovery (22.5%); Sustainability, climate and nature (19.8%); Culture, heritage and experiences (12.7%) | small source cell |
| 2019 | 132 / 28 | Sustainability, climate and nature (30.6%); Culture, heritage and experiences (15.6%); Demand, performance and recovery (15.2%) |  |
| 2020 | 139 / 37 | Health, safety and crisis resilience (72.5%); Sustainability, climate and nature (27.9%); Policy, visas and travel facilitation (18.7%) |  |
| 2021 | 119 / 44 | Health, safety and crisis resilience (57.6%); Sustainability, climate and nature (28.3%); Demand, performance and recovery (16.0%) |  |
| 2022 | 113 / 29 | Health, safety and crisis resilience (52.2%); Sustainability, climate and nature (35.4%); Demand, performance and recovery (25.6%) |  |
| 2023 | 123 / 20 | Sustainability, climate and nature (40.7%); Health, safety and crisis resilience (27.2%); Demand, performance and recovery (20.3%) |  |
| 2024 | 163 / 16 | Sustainability, climate and nature (34.9%); Culture, heritage and experiences (25.4%); Health, safety and crisis resilience (23.9%) | small source cell |
| 2025 | 89 / 29 | Sustainability, climate and nature (36.9%); Demand, performance and recovery (24.0%); Health, safety and crisis resilience (24.0%) |  |
| 2026 | 16 / 22 | Sustainability, climate and nature (39.2%); Health, safety and crisis resilience (36.1%); Demand, performance and recovery (34.4%) | partial year |

## Brands and associations

| Name family | Articles mentioning name | Sources | Most frequent same-sentence theme |
| --- | --- | --- | --- |
| Hilton | 146 | 6 | Transport and connectivity (16 articles) |
| Marriott | 136 | 5 | Transport and connectivity (17 articles) |
| Sabre | 104 | 4 | AI and digital technology (79 articles) |
| Expedia | 95 | 5 | AI and digital technology (13 articles) |
| Hyatt | 86 | 5 | Culture, heritage and experiences (9 articles) |
| IHG | 84 | 6 | Transport and connectivity (10 articles) |
| Dusit | 83 | 2 | Sustainability, climate and nature (51 articles) |
| Accor | 83 | 5 | Sustainability, climate and nature (11 articles) |
| Amadeus | 81 | 5 | Sustainability, climate and nature (11 articles) |
| Tripadvisor | 79 | 4 | Sustainability, climate and nature (12 articles) |

Association dispositions: **2,128** same-sentence co-occurrences, **1,716** window-only matches, and **97** career-context cautions. Counts concern literal name families; the dictionary is non-exhaustive and does not map historical corporate ownership. Even same-sentence evidence does not establish a partnership, ownership, reputation or causation. A high count can reflect repeated member announcements.

## Sentiment and unsupervised themes

TextBlob and VADER agree on **59.55%** of the theme-context labels. This is model agreement, not accuracy or public opinion. Sentiment remains an optional exploratory diagnostic; disagreement and non-target-specific contexts are recorded individually in `sentiment_comparison.csv`.

**7 of 15 NMF clusters** have at least 80% of assigned articles from one source. Cluster terms can reflect publisher vocabulary, brands and recurring formats as well as topics. The model is descriptive evidence, not an independent validation of the codebook. All labels, concentrations and examples are in `nmf_cluster_review.csv`.

## Extraction, dates and coding limits

| Flag | All records | Eligible records |
| --- | --- | --- |
| structured_conflict | 0 | 0 |
| body_not_well_supported_by_raw_html | 4 | 0 |
| raw_headline_disagreement | 4 | 0 |
| navigation_or_byline_in_body | 4 | 1 |
| pdf_replacement_characters | 5 | 0 |

Raw-text containment corroborates provenance, not completeness or truth. PDF front-matter checks do not certify layout. Parent-page dates remain explicitly identified. Excluded records and their raw files are retained for reproducibility.

The alternate headline/lead probes found **224 possible missing theme assignments**. Broad cues such as technology, software, booking or security are candidates rather than accepted labels; some are ambiguous brand names or do not meet the specific codebook definition. `candidate_missing_themes.csv` preserves them. The audit does not estimate semantic precision or recall.

## Reproduce and inspect

Run `python run_research.py --offline` to apply local corrections, rebuild changed analysis and audit; run `python run_research.py --audit-only` to recheck an already published current snapshot. Both commands resume saved work. `AUDIT_REPORT.md`, `summary.json`, `audit_state.json` and `../QUALITY_CHECKS.json` document completion and evidence. See `../../docs/AUTOMATED_VALIDATION.md` for all decision rules.