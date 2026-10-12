# Historical discovery and coding follow-up — 2026-10-12

This is an implementation and evidence log. The professor-facing final report is outside this task. Automatically generated exploratory analysis and audit artifacts remain part of the pipeline.

## Latest rerun and overall completion

The subsequent normal rerun `20261012T065126Z-5aec3f63` finished on 12 October with launcher exit **0** and `available_scope_processed`. Setup and dependency checks passed; all available source queues were resumed with zero new eligible articles and zero collection errors. The audit was rerun across all 5,659 saved documents and completed with zero errors. The analysis did not need rebuilding: the published analysis remains `20261012T025127Z-1439a726`. CTO and Travel Weekly again returned HTTP 403, so the successful process exit means available work was processed, not that all requested sources were obtained. Curation emitted a non-fatal Beautiful Soup `XMLParsedAsHTMLWarning`; the phase completed with zero errors and zero record updates. It is a parser/logging warning, not an access bypass or evidence that new data were collected.

The project therefore has a working, tested, recoverable collection/analysis/audit system and completed automated review for the data on hand. It has **not** met the substantive target of a ten-year, nine-source dataset: six sources contribute core articles, historical coverage varies substantially by source, three sources have no core articles, and Hospitality Net contributes only 2026 material. Thematic, source-focus, brand and sentiment outputs exist as exploratory analysis, with sentiment agreement and keyword mentions explicitly not presented as validated accuracy or stance. No professor-facing final report was prepared, per task scope. The concise status matrix is in the [README](../README.md#project-status--12-october-2026).

## Completed run and scope

The analysis snapshot `20261012T025127Z-1439a726` was published after processing the available collection queues. Its original run exited **2** with `partial_needs_followup` because CTO and Travel Weekly returned HTTP 403. The later 06:51 rerun described above resumed those checkpoints, again received 403, and exited **0** because no other discovered work remained. There are no pending candidate URLs or cooldowns. `analysis_current` is true; `study_complete` and `research_validated` remain false.

The finished snapshot has **5,659 saved documents, 5,105 eligible records, 4,829 core article occurrences, 257 supplementary reports and 1,124 current-window articles**. Six of nine sources contribute core articles. Counts by source are UN Tourism 1,305; WTTC 659; PATA 1,731; AHLA 286; ETC 260; Hospitality Net 588. IH&RA, CTO and Travel Weekly contribute no eligible core articles. The fixed English-language study window remains 2016-10-10 through 2026-10-10. Calendar 2016 and 2026 are partial years. No tenth source was added: the brief lists nine URLs.

For Hospitality Net, all 40 currently linked archive pages were traversed. Its 588 eligible core articles span 2026-07-23 through 2026-10-09; all are from 2026. Historical years remain missing. The other source/year gaps are preserved in `output/audit/coverage_audit.csv` and the analysis coverage tables; an absent observation means data were not collected, not that the topic was absent.

The full audit reviewed 5,659 documents, 20,524 theme assignments, 6,006 entity rows, 3,941 brand associations, 20,524 sentiment rows and 15 NMF clusters. All eight audit consistency checks passed with zero errors. All 22 structural checks passed. The machine-readable summary is `output/audit/summary.json`; the report remains exploratory and is not the professor-facing final report.

## Archive routes checked

| Source | Public route and discovery mechanism | Interpretation |
|---|---|---|
| Hospitality Net | `/llms.txt` identifies `/news` and `/opinion`. Their HTML links to `/news/page/2` and `/opinion/page/2`, each ending at page 20. | All 40 linked pages traversed. The news tail is September 2026 and opinion tail July 2026. This improves the current sample but does not recover ten years. The 13-entry current news sitemap was insufficient. |
| WTTC | `/news` and `/blog`; published JavaScript stores `?page=N` in browser history but loads pages with a read-only JSON POST to `/component/search/index`. | A direct GET ignored the page number. The adapter uses the actual public search request, then verifies the active page number. Each request body has a separate cache/failure identity. Pages 1 and 2 were verified live before the full walk. |
| PATA | `/blog`, `/press-release`, `/member-chapter-news-1`; follow actual `rel=next` offset links. | Never synthesize offsets or use robots-disallowed JSON endpoints. Completion only covers the surviving public collections. |
| AHLA | `/news` follows `rel=next`, initially through page 42 (43 pages). | The oldest pages include membership/resource pages with dates; a dated listing is not proof of a news article. Extraction and curation eligibility remain necessary. |

Each page and its queue insertions commit together. A failure leaves the failed page at the front of the saved cursor. Repeated article sets, pagination cycles, external next links and unrecognized templates fail visibly. Existing successful URLs are retained. At most 250 archive pages per source are traversed in one invocation; the same command resumes the remainder. Requests remain sequential and at least three seconds apart, respecting longer crawl delays and cooldowns.

The HTTP layer now interprets wildcard and end-anchor robots rules. This matters for Hospitality Net's filtered queries, PATA's `format=json` routes and AHLA's PDF restrictions. Permission reported by the user does not turn a failed HTTP request into collected data.

The expanded Hospitality Net sample exposed boilerplate and tag contamination. Post-extraction curation now selects `article section[aria-label="Main content"]` from saved HTML, excluding the company About section, topic tags, publisher profile and header metadata. It recomputes word counts and content hashes, preserves raw files and is idempotent. This avoids a full re-extraction of unrelated sources.

## Sources still requiring accessible material

- **CTO:** the official home and recent releases are visible through web search, but the local crawler previously received HTTP 403 at robots access. [Official home](https://www.onecaribbean.org/) and [contact/source description](https://www.onecaribbean.org/contact-cto/) confirm the publisher. Search visibility is not an export or evidence that the crawler can fetch it. The 2016 annual-report sample is a report, not a substitute for a decade of article discussion.
- **Travel Weekly:** the [official news listing](https://www.travelweekly.com/Travel-News) is visible through web search, while local automated access was held after HTTP 403. Searches for feeds/licensing largely returned articles discussing other companies' feeds; those are not Travel Weekly archive exports. No verified ten-year downloadable export was found.
- **IH&RA:** the [press-release page](https://ih-ra.com/ihra-press-release/) contains 2014 releases; the home refers to 2016 events before the study cutoff. The legacy `ih-ra.org` pages found refer to substantially older association material, and its home returned a retrieval error. The similarly named Japanese service association and the motor-racing IHRA are different organizations and are not substitutes. Hotel-directory links are not association news. No defensible in-window corpus was established from these routes.
- The brand-list reference supplied in the brief, `https://www.globalbrandsmagazine.com/tourism-brands-in-the-world/`, returned HTTP 403 during this check. The project therefore does not claim its entity dictionary reproduces that list.

A deliberate local access recheck for CTO and Travel Weekly is included in the expansion run. Renewed denials remain durable holds, without repeated hammering. No emails, subscriptions, purchases or access requests were sent.

An ordinary-browser access check was also attempted through the available browser-control tool; it reported **no browser available**. Therefore no successful browser fallback or browser-based corpus is claimed.

## Codebook 0.6

Reviewed the 323 omission probes in the prior audit using the saved article context. Specific concepts were added: ecotourism, renewable energy, waste reduction, wildlife conservation; software, digital tools/identity and hotel/travel technology; employees, workers, recruitment, staffing and wages; travel intentions/sentiment, hotel demand and booking trends; vacation rentals, business models, reservation systems and distribution platforms; vaccination and safety/cleaning protocols.

Bare `booking`, `security`, `conservation` and `technology` probes are not accepted wholesale. Examples include booking-platform mentions that do not measure demand, food security, and Labour Day travel that is not a workforce discussion. Regression tests preserve these distinctions. Assignment still means a concept mention; the separate focus evidence distinguishes central discussion from incidental references. This is not ground-truth accuracy certification.

All 323 prior omission probes have a row-level disposition in [CODING_REVIEW_2026-10-12.csv](CODING_REVIEW_2026-10-12.csv): 156 are now covered by a specific concept rule and 167 remain unpromoted from ambiguous probes. This is a deterministic review of the prior snapshot, not an estimate of precision/recall. The fresh audit may find additional candidates as the corpus expands.

Added candidate hospitality technology name families Cendyn, Cloudbeds, Mews, Agilysys, Duetto, SiteMinder, Oracle Hospitality and ForwardKeys. Mews is case-sensitive to avoid the ordinary housing term; bare Oracle is not treated as Oracle Hospitality. No retrospective ownership mapping is applied. The dictionary is explicitly non-exhaustive.

## Run and resume

Validation of the implementation: **68 offline tests passed**, with machine-readable results in `tmp/qa/junit.xml`. Tests cover archive cursor recovery, completed-walk cache reuse, repeated/template failures, distinct JSON search request caches, wildcard robots rules, extraction cleanup and coding negatives. A preview of 30 newly collected Hospitality Net articles retained structured date support for all 30 and removed 2,832 words of header/boilerplate/tag material; the full audit remains the authoritative all-record check.

```powershell
Set-Location -LiteralPath 'D:\Tourism-and-Hospitality-Industry-Trends'
python run_research.py --sources hospitalitynet wttc pata ahla
```

Repeat the same command after an interruption. For a deliberate one-time recheck of previously blocked sources:

```powershell
python run_research.py --sources cto travelweekly ihra --retry-blocked cto travelweekly
```

Analysis and audit always include the entire local corpus, even when collection is limited by `--sources`. `--offline` rebuilds from saved material; `--audit-only` audits the published snapshot. Use the normal command to resume an unfinished collection queue. Current completion, counts and error details are authoritative in `output/runner_summary.json`, `output/run_summary.json`, `output/QUALITY_CHECKS.json` and `output/audit/summary.json`. While a run is active, published results may describe the preceding snapshot.
