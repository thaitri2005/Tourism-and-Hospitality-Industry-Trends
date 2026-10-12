# Review of the completed crawl, 11 October 2026

The submitted run succeeded operationally. It is a useful exploratory corpus of three publishers, but it does not complete the requested nine-source, ten-year study. An empty queue means that known candidates were processed; it does not establish that discovery found every article.

## Follow-up recovery verified

Historical snapshot: later collection expanded the corpus and the [automated audit](AUTOMATED_VALIDATION.md) now checks every saved record and published assignment. Use `output/audit/summary.json` and the current analysis snapshot for current counts; manual-review tasks below describe the earlier handoff.

The user's subsequent run `20261011T072017Z-58997037` completed at **07:25 UTC / 14:25 Vietnam time** on 11 October. It replayed 117 cached archive pages, discovered all **62 missing article URLs**, and downloaded/extracted all 62 without errors. **61 were eligible**. The remaining item, “PUTTING PEOPLE FIRST: All UNWTO events planned until 30 April are suspended” (14 March 2020), is an 81-word English announcement excluded by the existing minimum-length rule. All 62 publication dates agreed with their saved archive hints.

The verified totals are **2,886 saved documents, 2,494 eligible records, 2,224 core article occurrences, 257 supplementary report records, and 169 current-window articles**. No candidates remain pending. The 22 structural checks passed; the database/code fingerprint, all 32 published artifact hashes, and the diagnostics ZIP's embedded audit matched this run. The saved archive reconciliation has **zero missing article links** and one unresolved index-page link. Repeating the recovery crawl is no longer necessary.

Log review also found 297 misleading `archive_candidate_excluded` warnings for genuine older `/archive/<region>/news/...` and `/press-release/...` articles. Every one was already extracted and retained in the database; 265 were eligible and 32 excluded by the normal analytical filters. The archive-link classifier has been corrected to distinguish those articles from an archive index, with a regression test. This correction does not change the current corpus or analysis. Historical logs are retained unchanged. The other warnings were the unresolved index link and the existing CTO access hold; there were no ERROR/CRITICAL events.

After that correction, **50 tests passed** and the full local audit again passed all **22 checks** against the same analysis snapshot. The README and diagnostic bundle were refreshed. No additional publisher requests or analysis rebuild were needed for this follow-up check.

## What the pasted output means

Run `20261011T053345Z-7a38f394` collected the outstanding work and published analysis. Run `20261011T062337Z-e9774ada`, shown in the pasted terminal output, correctly reused those checkpoints. Its `attempted: 0`, `remaining: 0`, and exit `0` were normal recovery behaviour. There was no fatal error or data loss in that rerun.

On arrival, the database held 2,824 documents: 1,424 UN Tourism, 780 WTTC, and 620 ETC. The original analysis used 2,164 article occurrences and 257 supplementary report records. These were the submitted snapshot's counts, before the review corrections below. The latest corrected totals are recorded in `output/run_summary.json` and `output/QUALITY_CHECKS.json`.

The offline correction retained all **2,824 raw documents**, with **2,433 eligible records**, **2,163 core article occurrences**, **257 supplementary report records**, and **168 current-window articles**. The expanded suite passed **49 tests**, and the corrected snapshot passed all **22 structural/numerical audit checks**. These checks are separate from the outstanding coverage and human-validation work.

## Confirmed defects and corrections

| Finding | Evidence and correction |
|---|---|
| Some UN Tourism archive articles were never queued | Reconciled all 117 saved archive pages. Of 1,392 cards within the study dates, **62 article links** were absent because they use flat slugs, `/global/`, `/node/`, or `/new/`. A dated headline card in the English news archive now permits these legacy routes while preserving source-host, language-route, and file-type restrictions. Ordinary sitemap filtering is not broadened to every page. The follow-up run recovered all 62. |
| One archive card points to an index | “UNWTO Workshop for Inbound Tour Operators”, dated 4 November 2016, links to `/archive/global/`. This is retained as an unresolved coverage issue in the audit; an index page is not substituted for an article. |
| A requested PDF became a homepage | Document `337e8512bb320c6736d4` is a PDF URL whose saved response redirects to the Best Tourism Villages homepage. It had been counted as 2021 news using the homepage date. HTML responses at PDF URLs now carry `unexpected_html_for_pdf` and are excluded, with the raw response retained for review. |
| Brand homonyms created false matches | Cultural Carnival events, lower-case “intrepid” travel descriptions, “four seasons”, and Emirates Council for Balanced Development appeared as brands. Conservative disambiguation rules now remove those observed errors. Brand recognition remains a non-exhaustive heuristic, with possible false positives and false negatives. Rules are exported in `theme_codebook.json`. |
| Headlines could be counted twice | UN article extraction often already contains the headline. Analysis now prepends a title only when it is absent from the extracted text, avoiding inflated name/keyword frequencies and duplicate sentiment weighting. |
| Long chart title was clipped | The ETC annual-theme chart title exceeded the available width. Chart titles now wrap to fit; source/year gaps and partial-year notes remain visible. |

No source restrictions were removed. No gated download forms were submitted. The initial review rebuilt existing records and analysis offline; the user's subsequent normal run then collected the 62 additional article links.

## Checks and their limits

The original snapshot passed SQLite integrity, document-to-queue reconciliation, decompression of every saved raw document, normalized body hashes, word counts, eligibility constraints, all 32 published artifact hashes, and the analysis input fingerprint. Its diagnostics ZIP also passed an archive-integrity check. This demonstrates storage and export consistency, not that every extracted sentence is accurate.

The added `research.validate` command independently checks a finished snapshot's record/artifact integrity, metadata references, deduplication keys, source/year counts, theme percentages, current-window source balancing, brand association arithmetic, sentiment alignment, NMF assignments, and saved archive omissions. Its JSON records the exact analysis run checked and separates coverage warnings from structural failures. It neither downloads documents nor performs independent human annotation.

Date review found one conflicting nonempty archive/date pair in the eligible submitted corpus: the redirected homepage above. The remaining matching hints are reassuring but not independent proof of date accuracy. Most UN Tourism dates come from visible page text and retain medium confidence. Cached header samples, extraction-length extremes, suspect homepage titles, and ambiguous brand contexts were inspected; this was a targeted assistant review, not a random accuracy study or a completed human-coded validation set.

## Remaining research gaps

- Only **UN Tourism, WTTC, and ETC** supply documents. PATA, AHLA, Hospitality Net, and Travel Weekly remain held under the recorded access review. IH&RA needs source verification. CTO remains blocked by the recorded HTTP 403. Access notes are in `research/config.py` and `RA_FEASIBILITY_PLAN.md`.
- WTTC's collected eligible articles begin in **March 2019**, leaving 2016–2018 unobserved. Exhausting the present sitemap does not establish completeness of its older archive.
- The saved UN archive exposes relatively few 2026 articles. After accounting for one missed legacy link, that low count is also present in the cached publisher archive; it cannot be interpreted as lower industry discussion. The site may not expose its complete publishing history there.
- **215 ETC download links are form-gated**. Supplementary report records mix landing-page summaries and accessible PDFs; they are not all full reports and are kept outside the main news/blog analysis.
- **Three permanent URL failures** were recorded as HTTP 404, including two ETC methodological-note PDFs and one UN action-plan PDF. These are known dead links, not evidence that retry recovery failed.
- 2016 and 2026 are partial boundary years. Some source/year samples are small. Coverage varies between publishers and over time.
- The extraction protocol also excludes short text: 111 otherwise eligible English records in the submitted snapshot failed only the length threshold (68 UN Tourism, 35 WTTC, 8 ETC). Some may be legitimate short statements. Review this exclusion before treating the analytic corpus as all available English discussion; language verification is also a heuristic.
- The top ten themes are ranked matches from a predefined 14-theme codebook. NMF is a separate exploratory check; its clusters still need substantive labels. Broad terms, publisher boilerplate, and promotional writing can affect the results.
- Sentiment is an **unvalidated TextBlob baseline** on theme-related sentences. Do not present it as reliable industry attitudes. Name proximity does not establish corporate ownership, a formal partnership, or the direction of a brand association.
- The brief says ten websites but supplies **nine**. The brand-reference page does not supply the missing tenth corpus source.

## What to do next

1. **The 62-link recovery is complete. No further run is required for it.** For future collection or resumption, the supported command remains:

   ```powershell
   Set-Location -LiteralPath 'D:\Tourism-and-Hospitality-Industry-Trends'
   python run_research.py
   ```

2. After that command exits, check the resulting snapshot and rebuild the diagnostic bundle:

   ```powershell
   .\.venv\Scripts\python.exe -m research.validate
   python run_research.py --diagnostics
   ```

   Inspect `output/QUALITY_CHECKS.json`; send `output/diagnostics/latest.zip` for review. A structurally passing audit can still warn about missing sources or inaccessible articles. The 62 URLs are candidates, not a promise of 62 additional eligible, unique articles.

3. Copy `output/tables/human_review_template.csv` outside `output/` before editing it. The current template selects 90 articles across available source/year groups. Review publication date, extracted body, topic assignments, and brand matches against original pages. Analysis overwrites the generated blank template, so retain completed annotations separately. Sentiment requires separate labeled examples before reporting accuracy.

4. For the one-week deadline, agree whether the deliverable can be a clearly labeled **three-source exploratory pilot** with a coverage appendix. Completing the broader brief also needs source access/export arrangements, the missing tenth-source decision, historical gap resolution, and human validation. Repeatedly running the crawler cannot resolve those decisions.

Use `output/PRELIMINARY_REPORT.md` for the exploratory findings and `output/figures/coverage.png` to explain the missing source/year cells. Do not submit the corpus as a comprehensive industry census.

## User-directed six-source follow-up

The later instruction explicitly asked to attempt PATA, AHLA, Hospitality Net, Travel Weekly, CTO, and IH&RA. Those six registry entries are now enabled for public-page research; the crawler retains its robots, same-host, rate-limit, and HTTP-denial checks. CTO and any other previously blocked source get one fresh access recheck, then a renewed denial is saved as a durable hold. This does not clear publisher reuse terms: PATA and AHLA currently state that automated collection needs prior express consent. The attempt follows the user's project instruction; review retention and sharing conditions before distributing collected text. IH&RA discovery targets the official press-release, industry-news, and newsroom archives pending source/date review.

The live follow-up `20261011T094342Z-e847eba6` refreshed discovery and collection, updated all extraction outputs, and published the analysis. Its structural audit passed all **22 checks**. The snapshot contains **3,730 documents, 3,263 eligible records, 2,992 core article occurrences, 257 report records, and 328 current-window articles**. Those are integrity-checked counts, not a complete industry census.

| Source | Result in this snapshot |
|---|---|
| UN Tourism | 1,486 extracted; 1,318 eligible (existing corpus retained) |
| WTTC | 780 extracted; 659 eligible (existing corpus retained) |
| ETC | 620 extracted; 517 eligible (existing corpus retained) |
| PATA | 482 extracted; 470 eligible; **1,351 candidates remain** in its 1,833-URL discovered inventory |
| AHLA | 301 extracted; 290 eligible; 47 linked files were skipped because robots.txt disallows the file paths |
| Hospitality Net | 15 extracted; 9 eligible from its sitemap/seed discovery |
| IH&RA | 46 extracted; 0 eligible for the English 2016-10-10 to 2026-10-10 corpus after date/language/text filters; further archive review is needed |
| CTO | No documents; its one fresh robots request returned HTTP 403, saved as a durable hold |
| Travel Weekly | No documents; its one fresh robots request returned HTTP 403, saved as a durable hold |

PATA's crawler was paused after a bounded collection segment to publish the updated interim analysis; the saved queue resumes with `python run_research.py`. The next run processes other sources first and PATA last because PATA has the large remaining queue. There are no pending AHLA candidates: its remaining 47 were robots-denied and marked terminal. Structural checks passed, but the report still flags only **six of nine registered sites with core articles**, 1,351 pending candidate URLs, incomplete historical coverage, and unvalidated coding/sentiment. The refreshed diagnostics archive is `output/diagnostics/latest.zip`.

## Slow crawl completion after professor permission

The user confirmed that the professor obtained permission for the requested academic crawl and asked that collection proceed slowly. The fetcher now enforces a minimum **3-second interval** between HTTP requests (or the longer applicable `robots.txt` delay). The source-specific robots, host allow-list, and HTTP-denial handling remain active. PATA PDF links that redirect to `static1.squarespace.com` remain rejected as off-host URLs; the redirect destinations are now explicitly logged. These per-URL external redirects and robots exclusions no longer count as repeated source failures, so one such link does not unnecessarily pause unrelated PATA article collection.

Run `20261011T125721Z-9795158c` completed on 11 October 2026 with status `available_scope_processed` and exit code 0. It attempted the 350 queued PATA URLs: 317 became eligible records, 17 URL-level errors were recorded, and no discovered URLs remain pending. The refreshed analysis covers **5,077 saved documents, 4,559 eligible records, 4,284 core article occurrences, 257 supplementary report records, and 551 current-window articles**. Six of nine listed websites currently supply core articles. CTO and Travel Weekly remain held after HTTP 403; this run did not bypass those responses. IH&RA has 46 saved records, but none pass the current English, date and text eligibility filters. The run summary, source/year tables and URL inventory contain the detailed coverage.

The local validator passed all **22 structural checks** with zero errors against analysis run `20261011T125721Z-9795158c`; its coverage warnings remain. The automated checks establish file/database consistency and arithmetic only. They do not independently certify extraction fidelity, historical completeness, topic coding, sentiment, or brand attribution. `output/diagnostics/latest.zip` was rebuilt after validation. Resume/check with `python run_research.py`; the configured slow request interval is used by that same command.

## Explicit retry of previously blocked sites

To address the user's report that an ordinary resume immediately reused old 403 holds, the launcher now supports `python run_research.py --retry-blocked cto travelweekly`. It resets only the named blocked sources' saved robots failure and discovery checkpoints, then performs a new normal access/discovery attempt. Regular reruns remain non-probing. A unit test verifies that only the selected hold and checkpoints are cleared; the full suite passes **51 tests**.

Run `20261011T144358Z-9caf6adb` exercised the option. Both fresh requests to `/robots.txt` still returned HTTP 403 (CTO in about 1.1 seconds; Travel Weekly in about 8.5 seconds). The crawler honored both denials and restored their persistent holds without attempting article pages. Its exit code 2 / `partial_needs_followup` correctly indicates the two source coverage gaps; the rest of the available corpus and analysis checkpoint remained intact. The subsequent structural audit passed all 22 checks with zero errors, and the diagnostics ZIP was refreshed. A later recheck can be explicitly requested with the same flag if access conditions change, but the current 403 response cannot be fixed from the crawler side.

## Content spot-check and final codebook refresh — 12 October 2026

A 16-record purposive spot-check compared saved articles across available source/time groups with official pages where accessible. Eleven original-page URLs were opened: nine rendered and two UN Tourism pages returned 403 in the independent review browser; their local saved bodies remain available but were not independently live-verified in that check. The PATA 2017 page did not display its year in the live rendering. A nine-source-period review note with record IDs, links and case-level observations is in `docs/CONTENT_QA_2026-10-12.md`. This is an assistant QA pass, not a random sample, second-coder validation, or a corpus-wide accuracy estimate.

Two concrete coding issues were corrected. A source/page titled only with “Secretary-General” or “chairman/chairperson” could trigger the partnership/governance category despite no story about governance or partnership. These two title-only patterns accounted for 671 historical tags, including 48 of the 551 current-window articles. They were removed; explicit words such as partnership, governance, general assembly and board of directors still count. The live WTTC biometrics article was strongly about technology but failed to trigger the AI/digital category, so `biometric(s)` was added. The updated codebook is version 0.4. These remain dictionary mentions, so incidental mentions and broad multi-tagging still require second-coder review.

The rebuilt offline analysis run `20261011T170801Z-ab905095` published 5,077 documents, 4,559 eligible records, 4,284 core article occurrences, 257 supplementary report records, and 551 current-window articles. The current-window candidate governance/partnership count fell from 219 (39.8%) to 171 (31.0%); this is a codebook sensitivity result, not a validated prevalence estimate. The report now describes NMF as a diagnostic because several large clusters are publisher/entity or format-driven. Sentiment remains an unvalidated TextBlob baseline. The 52-test suite passed, and all 22 structural checks passed with zero errors; coverage warnings remain for only 6/9 sources supplying core articles and one unresolved archive card. `output/QUALITY_CHECKS.json` identifies the final analysis run.

A genuinely complete validation still needs independent annotation: select a documented held-out sample, have a reviewer verify dates/text and assign primary topics/entity relevance without seeing the model's output, calculate agreement and resolve discrepancies, then revise the dictionary/model and sentiment approach as indicated. The current 146-row generated review template is intentionally blank; the documented assistant spot-check does not fill or replace it. Missing/blocked sources and unsupported historical archive years also remain coverage gaps.
