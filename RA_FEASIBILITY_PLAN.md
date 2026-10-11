**Tourism and hospitality discourse study — feasibility and proposed implementation**

Prepared for Trí from Jenny Le’s RA brief. Source checks: 10 October 2026, Vietnam time.

The study is technically feasible. Its defensible scope is the themes, expressed sentiment, and brand associations in a selected set of industry websites. It will not measure the opinions of all tourism professionals or consumers. Complete historical coverage and permission to collect all requested sources cannot yet be promised.

This is a feasibility audit and implementation proposal. It is not a completed crawl, an article inventory, or a set of measured industry findings. Dates below are examples found during inspection, not certified archive start dates or evidence of uninterrupted coverage.

**Scope to settle before the full collection**

The brief names nine collection websites, although it asks for ten. Global Brands Magazine is supplied separately as a brand reference; it should not silently become the tenth research source. The list combines seven institutional/association sources with two trade media platforms. Analyze these source classes separately as well as together.

Recommended starting specification:

- English-language public news, press releases, and substantive industry articles.
- Six complete years, 2020–2025, for the first historical analysis; extend to 2016–2019 where coverage can be established. This preserves the pandemic period while making the first delivery manageable.
- A separate current-discussion window covering the latest 12 months to an agreed cutoff. Show 2026 as a partial year, not as directly comparable annual volume.
- Reports and PDFs as a separately identified supplementary corpus. Do not give a 100-page report 100 times the weight of an article.
- Exclude menus, directories, advertising blocks, job listings, routine event registrations, and generic membership pages from the core thematic corpus. Substantive event coverage can remain.
- Interpret “brand associations” initially as brands linked to themes and other named entities in text. Keep organizational membership, ownership, and partnerships separate from textual co-occurrence.

**What the source inspection found**

| Source | Evidence and useful entry points | Proposed treatment and unresolved issue |
|---|---|---|
| UN Tourism / UNWTO | The [news archive](https://www.untourism.int/news?page=115) exposes dated October 2016 items. Useful for institutional tourism discourse. | Promising historical source. Resolve old UNWTO URLs and translations to canonical documents. Its [copyright page](https://www.untourism.int/copyright) describes personal, non-commercial use with redistribution/derivative-use restrictions; establish the research collection and retention basis before bulk processing. |
| WTTC | A public [news section](https://wttc.org/news), topical reports, and a dated [May 2020 release](https://wttc.org/news/wttc-unveils-safe-travels-new-global-protocols-to-restart-the-travel-tourism-sector) are available. | Strong candidate for economic, policy, and business discussion. Pre-2020 news completeness remains unverified. [Terms](https://wttc.org/terms-and-conditions) include an academic-research provision subject to acknowledgment and applicable conditions. Confirm bulk collection/storage scope and document-specific licenses. |
| IH&RA | The supplied [homepage](https://ih-ra.com/) mixes old association material with extensive hotel listings. Its [press-release page](https://ih-ra.com/ihra-press-release/) contains a March 2014 association release. | Quarantine from automated inclusion until the organization confirms the appropriate source/archive. This observation does not establish who operates the site or why the listings are present. A trustworthy current time series is not established. |
| PATA | Separate [press releases](https://www.pata.org/press-releases), member/chapter news, and blog sections. A [November 2020 article](https://www.pata.org/press-release/asia-pacific-saw-moderate-growth-of-international-arrivals-in-2019-before-collapsing-in-early-2020) is readable. | Useful Asia-Pacific material; distinguish PATA-authored and member-submitted content. Pre-2020 completeness unverified. Its [terms](https://www.pata.org/terms-conditions) restrict automated monitoring/copying without express consent. Seek a research export or authorized collection. |
| AHLA | Public [news](https://www.ahla.com/news), an [indexed 2016 archive page](https://www.ahla.com/news?mstr=650&page=42), and a [2016 annual report](https://www.ahla.com/sites/default/files/AHLAAnnual_2016.pdf) provide historical leads. The archive result also contains membership pages, so a date alone is insufficient for inclusion. | Useful US lodging perspective. The archive page appeared in search, but a direct follow-up retrieval failed in this audit. [Terms](https://www.ahla.com/ahlacom-terms-use) restrict scraping/monitoring/copying without express consent. Confirm access and inspect original dates. |
| ETC | A substantial [press centre](https://etc-corporate.org/press-centre/) and publication collection. A [July 2016 news release](https://etc-corporate.org/news/etc-publishes-new-quarterly-report-7/) and [2016 report landing page](https://etc-corporate.org/reports/european-tourism-2016-trends-prospects-q3-2016/) are available. | Promising pilot source for European tourism discussion and reports. Separate article publication dates from the years covered in reports. Individual report notices govern reuse; the [2016 Q2 report](https://etc-corporate.org/uploads/reports/ETC-Quarterly-Report-Q2-2016_Public.pdf) distinguishes internal reproduction from public distribution. |
| CTO / OneCaribbean | Public [CTO news](https://www.onecaribbean.org/media/cto-news/) and [annual reviews](https://www.onecaribbean.org/statistics/annual-reviews-prospects/). The review page includes 2016 performance discussed in February 2017. | Useful regional material. Historical reports exist, but a complete 2016–2025 news archive is not yet established. Split multi-year compilation pages into individual dated items; do not label the entire page as one year's discourse. Establish collection/reuse conditions. |
| Hospitality Net | Readable [2016 material](https://www.hospitalitynet.org/news/4077798/hftp-launches-new-association-focused-news-site-hftp-news), [RSS feeds and an API inquiry route](https://www.hospitalitynet.org/rss), and a [brand directory](https://www.hospitalitynet.org/brands). Content includes releases, commentary, and some short summaries linking elsewhere. | Valuable for brands and hotel operations. Request an authorized historical export/API arrangement. [Terms](https://www.hospitalitynet.org/terms-conditions) restrict automated access without permission and bulk extraction; the relatively permissive [robots file](https://www.hospitalitynet.org/robots.txt) does not resolve those restrictions. Track full text versus teaser-only records and original publishers. |
| Travel Weekly (.com) | A readable [December 2016 year review](https://www.travelweekly.com/Travel-News/Travel-Agent-Issues/2016-Year-in-Review) and [historical search listings](https://www.travelweekly.com/Search?pg=2546) show valuable older trade coverage. | Technically promising, but publisher [terms](https://adhost1.ntmllc.com/twxads/T%26C.htm) restrict automated collection and electronic retention without authorization. Use a publisher agreement or a library resource with appropriate text-mining rights. Keep .com separate from similarly named publications on other domains. |

The [Global Brands Magazine reference URL](https://www.globalbrandsmagazine.com/tourism-brands-in-the-world/) could not be retrieved through the research tool. Its contents and ranking methodology were not verified. Treat it as an optional seed list if recovered; supplement it with entities actually found in the corpus and verified official brand portfolios.

Robots checks were attempted for all nine domains. The research tool returned readable robots files for WTTC and Hospitality Net; the other attempts failed through that tool. This is not evidence that those sites lack robots files or prohibit all access. Sitemap locations were advertised in the two readable files, but sitemap retrieval did not succeed through the tool. Operational discovery and permission checks remain part of the pilot.

**Collection and data design**

Use a small Python project with one adapter/configuration per source, a shared extraction pipeline, and reproducible analysis scripts. A full web application is unnecessary for the first delivery.

1. Maintain a source register: allowed domains and paths, source class, entry pages, permission/license evidence, permitted retention/sharing, robots snapshot, and crawl settings.
2. Discover URLs through authorized exports/APIs, sitemaps, archive pagination, and RSS. RSS is useful for updates but should not be assumed to contain a decade of history. Search engines help locate missing routes, not establish a complete population.
3. Fetch permitted content with caching, resumable jobs, bounded retries, low per-domain concurrency, and backoff on rate limits. Use browser rendering only when ordinary HTML retrieval cannot expose permitted content.
4. Extract title, article body, author, publisher, language, source section, dates, tags, and canonical URL. Remove boilerplate. Use a source-specific fallback when generic extraction fails.
5. Preserve publication date, modified date, report coverage period, and crawl date separately. Never substitute a search engine's “published” estimate or sitemap modification date for an original article date without validation. Undated or conflicting records need explicit flags.
6. Deduplicate exact copies and near-identical syndicated releases. Keep both a unique-story identifier and each website's occurrence of that story. This supports unique-story trends and separate website publishing profiles without losing provenance.
7. Produce a source-by-year coverage matrix: discovered, fetched, relevant, full-text, reliably dated, duplicates, failures, and exclusions. Missing data must remain missing, not become a zero-topic observation.

Suggested logical tables:

| Table | Essential fields |
|---|---|
| sources | source_id, organization, domain, source_class, access_status, license_evidence, discovery_routes |
| documents | doc_id, canonical_url, title, body_or_authorized_reference, published_at, modified_at, date_evidence, date_confidence, coverage_period, language, content_type, text_completeness, original_publisher, retrieved_at, content_hash, duplicate_cluster_id |
| occurrences | occurrence_id, doc_id/story_id, source_id, source_url, source_publication_date |
| topic_assignments | doc_id, theme_id, evidence_span, score, model_version, review_status |
| entity_mentions | doc_id, entity_id, surface_form, entity_type, character_offsets, evidence_context |
| sentiment | doc_id, theme_or_entity_id, evidence_span, sentiment_label, uncertainty, model_version, review_status |
| crawl_log | requested_url, timestamp, response_status, extraction_status, retry_count, exclusion_reason |

Keep permitted raw files separate from cleaned text and derived outputs. Raw text should not automatically be included in a public deliverable. Exclude unrelated contact details from analytical exports.

For implementation, [Scrapy AutoThrottle](https://docs.scrapy.org/en/latest/topics/autothrottle.html) provides adaptive crawl pacing, and [Trafilatura](https://trafilatura.readthedocs.io/en/latest/) extracts article text and metadata. Use a PDF parser for the optional reports layer and OCR only where necessary. Parquet plus DuckDB or SQLite is sufficient storage for an initial research corpus. Pin dependencies and record extraction/model versions.

**Mapping the requested insights to methods**

| Requested insight | Proposed analysis | Deliverable |
|---|---|---|
| Ten current themes | Discover candidate clusters from a sample balanced across sources and years, inspect representative passages, then define a human-reviewed theme codebook. Assign multiple themes where justified. Rank themes within the explicitly defined current window. | Ten leading themes with definitions, article shares, source counts, and traceable examples. |
| Themes over 5–10 years | Apply the same theme definitions across the full period; calculate within-source annual shares, then summarize consistently. Inspect changing subtopics and vocabulary separately. | Year-by-theme heatmap, annual top themes, and trend charts with coverage notes. |
| Themes by website | Compare each website's theme proportions and its distinctive concentration relative to the other sources. Show institutional and media strata. | Website-by-theme matrix and short evidence-backed profiles. |
| Brands and associations | Combine named-entity recognition with a curated alias dictionary; normalize corporate groups, consumer brands, properties, and trade organizations separately. Analyze paragraph/sentence co-occurrence. | Brand rankings by unique-document count, brand–theme matrix, and an optional network with supporting passages. |
| Optional sentiment | Classify sentiment or stance toward a specific theme/brand in the relevant passage; allow positive, negative, neutral, mixed, and uncertain/abstain. | Theme-level sentiment distributions with denominators and measured validation quality. |

Use a transparent TF-IDF/NMF baseline and an embedding-based candidate such as BERTopic. [BERTopic's time analysis](https://maartengr.github.io/BERTopic/getting_started/topicsovertime/topicsovertime.html) starts with a shared global topic model and then estimates time-specific representations. Independently fitting ten topics for every year would make the topic labels difficult to compare.

BERTopic clustering alone is not a validated multi-label theme classifier. After exploratory discovery, create explicit inclusion/exclusion rules and validate the chosen classifier or rules against human labels. An LLM can assist labeling and evidence extraction, but its suggestions need review, reproducible prompts/model identifiers, and held-out evaluation. Use only text processing arrangements allowed by the source agreements.

Possible starting concepts include sustainability/climate; AI and automation; digital marketing/social media; labor and skills; travel demand/economic performance; health and crisis resilience; destination management/overtourism; guest experience/personalization; distribution/business models; and inclusion/accessibility/community benefits. These are coding candidates, not findings or a preselected top ten. Discovery may split, merge, replace, or add concepts. Retain an “other/emerging” category instead of forcing everything into ten buckets.

For theme prevalence, use:

`theme_share(source, year) = relevant eligible documents assigned that theme / all eligible documents for that source and year`

Multiple themes may apply to an article, so shares need not sum to 100%. Report both the article-weighted view and an equal-source view, and show the denominator. For longitudinal comparisons, use a stable set of adequately covered sources where possible; an equal-source average can still shift artificially if its membership changes. Include sensitivity checks for duplicate handling, reports, and press-release-heavy sources. Weighting cannot correct unknown missing archives.

For brands, count distinct documents rather than repeated mentions within one document. Use curated aliases with [spaCy's rule-based matching](https://spacy.io/usage/rule-based-matching), plus contextual entity recognition. Resolve ambiguous names and separate parent groups from brands/properties. If ownership changes during the period, use dated mappings rather than assigning today's owner retrospectively. Identify brand–theme associations using relevant textual context, minimum document support, and an association measure that accounts for common brands/themes. Textual association is not proof of a commercial relationship, reputation, or market share.

Whole-article sentiment is a weak fit for this corpus: an article can welcome AI adoption while warning about employment effects. Analyze those targets separately. Official releases and promotional articles may systematically use positive language. The valid interpretation is sentiment expressed in these publications, not consumer satisfaction or industry-wide opinion. Report sentiment as exploratory if human validation is weak.

**Pilot and quality checks**

Proposed first milestone: 300–500 eligible documents from sources whose collection basis has been established, spanning early, middle, and recent periods. Include different content types and sources; do not sample only current homepages. Thin sources should be flagged rather than artificially filled.

The pilot should produce a URL inventory, access/source register, source-by-year coverage table, extraction examples, duplicate examples, initial theme codebook, and one draft chart for each core research question. It should also measure fetch time, extraction failures, text lengths, and model runtime so the full estimate can be revised.

Suggested acceptance checks, to agree with the supervisor:

- Every analytical record has source provenance, a stable identifier, and an explicit date-confidence status.
- A manually inspected sample across all tested sources/templates meets a proposed 95% target for usable main text and correct dates; failures are fixed or excluded and reported.
- No unresolved source identity issue, boilerplate-heavy record, or teaser-only item is silently treated as full-text evidence.
- A held-out labeled sample evaluates theme assignments and entity extraction with precision/recall/F1, including performance by important source/year strata. Avoid using the same examples for tuning and final validation.
- For sentiment, label approximately 200–300 theme/brand passages initially; double-code a subset with another reader and adjudicate disagreements. Expand the sample where needed for per-class estimates. Report performance by class rather than accuracy alone.
- Human review checks representative and borderline examples for every reported theme. Preserve concise permitted evidence excerpts or source links so claims can be traced.

**Effort, resources, and deliverables**

These are planning estimates for one capable Python/NLP RA, not measured project costs. Permission and archive-export waiting time is additional.

| Work package | Indicative effort |
|---|---:|
| Finalize scope/access register and complete a small pilot | 20–35 hours |
| Source adapters, historical discovery, cleaning, date checks, deduplication | 35–60 hours |
| Themes, year/source comparisons, brand normalization and associations | 30–45 hours |
| Human validation, charts, methods note, and final report | 25–40 hours |
| Optional validated sentiment layer | 15–25 hours |

Allow roughly 120–200 hours overall depending on sentiment, archive condition, and report inclusion: approximately four to six working weeks, or longer as a part-time RA assignment. Re-estimate after the pilot. A guaranteed ten-site, ten-year census or publication-ready validation may take longer.

Start on a normal development laptop. A GPU, paid model API, cloud server, and dashboard are optional. Open-source/local methods can avoid model API charges; publisher licenses and data exports may have separate costs that have not been quoted. Measure storage/compute needs after the pilot rather than buying infrastructure in advance.

Expected final package:

- Clean analytical dataset and data dictionary, within permitted sharing terms.
- Source/access register, coverage matrix, crawl/extraction logs, and exclusions.
- Versioned theme codebook, brand alias/hierarchy table, and validation results.
- Current top-ten themes; annual theme trends; website theme profiles; brand–theme associations; optional sentiment results.
- A concise research report with traceable examples, methodological limitations, and reproducible scripts/notebooks.

**Recommended decision**

Proceed with a bounded feasibility pilot and treat content access as the first workstream. Prioritize ETC and WTTC for initial tests after confirming applicable conditions, resolve UN Tourism's research use, seek approved exports/collection from PATA, AHLA, Hospitality Net, and Travel Weekly, and verify IH&RA's appropriate archive. A publisher data export may be faster and more complete than developing a crawler. If a source cannot be included, document the gap and agree on an alternative with Jenny; do not substitute silently.

The decisions to take to Jenny are the missing tenth source; exact date window and language; inclusion of PDFs/member submissions/sponsored content; the intended meaning of brand associations; deadline and RA hours; and whether she or the university can arrange research access. No messages have been sent to publishers or the supervisor, and no bulk corpus has been collected during this assessment.
