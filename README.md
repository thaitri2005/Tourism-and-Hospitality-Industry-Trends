# Tourism and hospitality industry discourse research

An executable first attempt at Jenny Le's RA brief: English material from **10 October 2016 through 10 October 2026**, from the nine supplied sources. The brief says ten websites but lists nine; Global Brands Magazine is a brand-reference lead, not a tenth corpus source. Both endpoint calendar years are partial. “Current” means 11 October 2025 through 10 October 2026.

This studies publisher discussion, not consumer or whole-industry opinion. Existing pilot data is retained. Always read the run status and snapshot identifiers below before using the outputs.

## Project status — 12 October 2026

The latest data snapshot predates the October 12 crawler policy update below. Its runner summary records CTO and Travel Weekly sitemap 403s and contains no articles from either source. Run `python run_research.py` to apply the URL-local 403 policy, migrate those old source holds, and resume discovery. The runner summary and logs will then show which permitted URLs were collected or individually denied.

| Part of the objective | Status |
|---|---|
| Resumable, slow, logged collection and analysis pipeline | Implemented and run; accessible/discovered queues are exhausted. |
| Nine requested publisher sources | The saved snapshot has core articles from **6 of 9** sources: UN Tourism 1,305; WTTC 659; PATA 1,731; AHLA 286; ETC 260; Hospitality Net 588. CTO and Travel Weekly have no articles in that snapshot; IH&RA yielded no in-window core articles. The updated collector continues across independent public URLs after a CTO/Travel Weekly 403. |
| Ten-year English-language collection (10 Oct 2016–10 Oct 2026) | **Partial.** Source/year gaps remain; Hospitality Net's 588 core articles are all dated 23 Jul–9 Oct 2026. Available archive exhaustion does not establish ten-year completeness. |
| Themes, annual/source focus, brands and sentiment | Generated and audited exploratorily for the collected corpus. Sentiment-model agreement is not sentiment accuracy; theme hits and brand co-occurrence are not validated stance or formal relationships. |
| Automated content and structural audit | Complete for the saved corpus: 5,659 documents, 20,524 theme assignments, 6,006 entity rows, 3,941 brand associations, 20,524 sentiment rows and 15 NMF clusters reviewed; all audit and structural checks passed. |
| Professor-facing final report | **Not prepared**; it was excluded from the requested work. |

Overall, the automated workflow is complete for material it could access, but the research objective is **partially complete**, not a nine-source ten-year census. The corpus snapshot contains **5,659 saved documents, 5,105 eligible records, 4,829 core article occurrences, 257 supplementary reports and 1,124 current-window articles**. See the [detailed progress and source/year gaps](docs/HISTORICAL_EXPANSION.md), [automated audit guide](docs/AUTOMATED_VALIDATION.md), and generated [audit findings](output/audit/FINDINGS.md). Structural checks passed; historical completeness and ground-truth semantic accuracy remain unestablished.

The 40 currently linked Hospitality Net news and opinion archive pages have been traversed. All 588 eligible core articles from Hospitality Net are dated **23 July–9 October 2026**; this expands current coverage but does not fill its 2016–2025 history. Coverage for every source/year, the 403 rechecks, codebook changes and audit limits are recorded in [the historical expansion log](docs/HISTORICAL_EXPANSION.md). This project snapshot is an audited exploratory dataset, not the professor-facing final report.

A later index-first public-web recheck found additional official CTO archive paths and historical Travel Weekly article leads, but did not add corpus rows. The updated crawler records a CTO/Travel Weekly 403 against that URL, then continues to independent configured public routes. See [the crawling-method recheck](docs/CRAWLER_RECHECK_2026-10-12.md) for scope and behavior.

## Start here: Windows / PowerShell

Use Python **3.12** and a normal PowerShell terminal. Internet access is needed for the first dependency installation and website collection. No API key, paid model, browser login, or virtual-environment activation is required.

**Copy and paste these two lines:**

~~~powershell
Set-Location -LiteralPath 'D:\Tourism-and-Hospitality-Industry-Trends'
python run_research.py
~~~

If the terminal already shows that project folder, the only command needed is `python run_research.py`.

1. Let the terminal stay open. The first run prepares Python packages automatically; later runs reuse them.
2. Watch for phase/progress messages. A heartbeat every 30 seconds means the process is still working even when a model or PDF takes time.
3. At the end, the terminal prints the exit code, summary path, and **“Send back this file”** with the diagnostics ZIP path.
4. Validation runs automatically; no annotation or manual approval is needed. If the run stops with errors, the ZIP contains the information needed to investigate.
5. Open `output/audit/FINDINGS.md` for the audited interpretation, `output/PRELIMINARY_REPORT.md` for the original exploratory tables, and `output/audit/AUDIT_REPORT.md` for audit details. Check the completion indicators below before using results.

**Run exactly the same command after an interruption or temporary failure.** Do not delete the database, cache, checkpoints, lock files, or `.venv` to restart. This reuses work already saved; it does not start the corpus over.

If Windows says `python` is not recognized, try `py -3.12 --version`, then use `py -3.12 run_research.py` consistently. If neither Python command works, install Python 3.12 with its command-line launcher first. If this project is in another folder, replace the path in `Set-Location`.

## What the command does

The launcher:

1. Creates `.venv` and installs/checks dependencies inside it. Setup output is logged; an interrupted installation is retried on the next invocation.
2. Acquires an operating-system lock, checks SQLite, and recovers interrupted items.
3. Resumes sitemap discovery, the English UN Tourism archive walk, and the linked news/blog archives for Hospitality Net, WTTC, PATA and AHLA. Successful discovery responses are cached; each archive page and sitemap frontier is checkpointed.
4. Collects permitted candidate articles and directly linked public PDFs. Each document commits separately. Successful URLs are skipped; incomplete downloads or cache mismatches are recovered.
5. Re-extracts saved documents only when the extractor changes, using local raw files, then applies logged, idempotent curation rules for confirmed content defects.
6. Builds the preliminary analysis, tables and charts. It stages the entire analysis before publishing files; unchanged, verified output is reused.
7. Audits every saved record and every theme, entity, association, sentiment and NMF result; tests source-weighting sensitivity; runs structural checks. Per-record audit checkpoints support recovery.
8. Writes a status summary and a shareable diagnostics ZIP, including when ordinary errors or Ctrl+C occur.

Sources run sequentially with at least 3 seconds between requests, or a longer robots crawl delay. Request reads time out after 35 seconds. Body size is capped at 30 MB. Runtime depends on archive sizes, publisher responses and analysis time. Keep the terminal open; a heartbeat appears every 30 seconds during long phases.

## Collect specific sources

For the remaining archive expansion, use this command and repeat **the same command** after an interruption:

~~~powershell
python run_research.py --sources hospitalitynet wttc pata ahla
~~~

The names after `--sources` set the collection order. Existing documents from every source remain in the analysis and automated audit. Omit `--sources` to process all nine configured sources. Do not run two collection commands at the same time.

Archive traversal follows publisher pagination, stops on repeated pages or changed templates, and saves a cursor after each successful page. The 250-page limit is per source per invocation; rerunning continues beyond that limit. A completed archive checkpoint means the currently linked archive was exhausted, **not** that ten years of publication history were recovered. Hospitality Net currently exposes only 20 news pages and 20 opinion pages, ending in 2026. See [historical expansion and source investigation](docs/HISTORICAL_EXPANSION.md).

Use `python run_research.py --status` while collection runs. Detailed `history_page_saved` events record the URL, candidate count, newly added URLs, next page and cumulative page count in `logs/runs/<run_id>/events.jsonl`.

## Stop and resume

Press **Ctrl+C once** and allow the process to finish writing its summary. Then run the same command again (including any `--sources` option). Closing the terminal or a hard crash can prevent final diagnostics, but committed documents and checkpoints survive; the next invocation recovers unfinished work. Logs are flushed on every event. A second lock protects against an orphaned child process if only its launcher was killed.

Alternatively, create `data/STOP`, or `data/STOP_untourism` for one source. Remove that marker yourself when ready to resume. The program does not silently remove intentional stop files.

An active second copy exits instead of collecting concurrently. Lock files may remain after exit; their presence does not mean a process still owns the OS lock. **Do not delete them.**

## Retry behaviour

| Situation | Automatic handling |
|---|---|
| Timeout, connection reset, HTTP 408/425/500/502/503/504 | At most three HTTP attempts for that fetch, with exponential backoff and jitter. After exhaustion, save a retry deadline at least five minutes ahead. |
| HTTP 429 or a transient response with `Retry-After` | Persist a source cooldown; never retry earlier than the server's deadline. Other sources can continue. |
| Rerun before a retry deadline | Keep the item pending and report the UTC deadline. Do not contact it early. Run the same command again after the deadline. |
| Five consecutive document failures | Pause that source for at least five minutes and continue with other sources. |
| HTTP 401 from CTO or Travel Weekly | Persist a source hold because the route requests authentication. For these sources only, a 403 is saved against the individual URL and skipped; other configured public URLs continue at the normal slow rate. |
| CTO or Travel Weekly robots rules or HTTP 403 | The user reports explicit academic permission for these two sources that supersedes their robots directives. The crawler records the robots response but does not apply its allow/disallow rules; it still uses the minimum three-second rate, host checks and per-URL 403 skips, and continues to other public URLs. A 403 `robots.txt` response is also handled as unavailable under [RFC 9309 §2.3.1.3](https://www.rfc-editor.org/rfc/rfc9309.html#section-2.3.1.3). |
| HTTP 404/410 or another permanent URL failure | Record it for review; do not retry it endlessly. |
| Extraction exception | Log the URL and full traceback. Retry automatically when the extractor code changes. |
| Changed extraction rules | Reprocess local raw documents with per-document checkpoints. |
| Corrupt/incomplete HTTP cache | Log the defect and fetch a fresh response when access permits. |
| Interrupted analysis/publication | Preserve the previous completed report where possible; verify the publication manifest and rebuild on the next invocation. |
| Interrupted content audit | Reuse completed record reviews whose data and audit-code fingerprints still match; rebuild aggregate audit outputs. |

Retry limits apply per fetch/invocation. A later identical command can try transient failures again after their saved deadlines. The program does **not** sleep for hours waiting for a cooldown. Persistent access holds and parser bugs need review; send the diagnostics bundle so they can be investigated.

## How to tell whether the run finished

Run `python run_research.py --status` in another terminal to inspect saved progress. This makes no network requests and is safe while collection is running. After the main command returns, `$LASTEXITCODE` in its PowerShell terminal shows the exit code.

| Exit code | Meaning | Next action |
|---|---|---|
| `0` | The requested operation finished. For a normal run, currently available/discovered work was processed. | Read the summary and send the ZIP. A setup-only run has not collected or analyzed anything. |
| `2` | Pending work, an incomplete phase, or an error needs follow-up. | Read the logged retry deadline; rerun after it, or send the ZIP for a persistent issue. |
| `130` | Interrupted by Ctrl+C or a stop marker. | Remove any intentional stop marker when ready, then rerun the same command. |
| `1` | Setup or a fatal failure prevented completion. | Send the ZIP or the current run's logs; rerun for a temporary installation/network failure. |
| `3` | Another instance holds the project lock. | Use/wait for the active terminal. Do not delete lock files. |

In `output/runner_summary.json`, check:

- `status`: what happened during this invocation, such as `available_scope_processed`, `partial_needs_followup`, `interrupted`, or `setup_complete`.
- `analysis_current`: whether this normal/offline invocation successfully published or verified analysis for its input snapshot.
- `progress.pending_urls`: the discovered article queue still waiting; this is not an estimate of undiscovered website content.
- `held_sources`, `blocked_sources`, `cooldown_sources`, and `errors`: the remaining constraints or issues.
- `study_complete`: deliberately `false`; complete historical coverage and ground-truth accuracy are not established by this software. This is separate from successful completion of the automated workflow.

Only treat the output file set as a successful publication when `output/analysis_state.json` has `status: "complete"`. Its artifact hashes are verified on the next run. If an update fails, older report files can still exist; their snapshot date is in `output/run_summary.json`. A setup-only run deliberately reports `analysis_current: false` and leaves prior research outputs untouched.

### Check the finished results locally

The complete automated audit runs after every normal or offline analysis. To rerun it on the published snapshot without crawling:

~~~powershell
python run_research.py --audit-only
~~~

It checks raw evidence, dates, extraction, all published semantic assignments, theme focus, brand context, sentiment disagreement, NMF source concentration and source-weighting sensitivity. It also runs the structural checks and writes `output/QUALITY_CHECKS.json`. `output/audit/audit_state.json` must say `complete`; `output/audit/summary.json` must say `process_complete: true` with no errors. `completed_with_limitations` is a completed automated review, with coverage and model limitations recorded explicitly. See [the audit guide](docs/AUTOMATED_VALIDATION.md) for every output and decision rule.

For structural checks alone, use `.\.venv\Scripts\python.exe -m research.validate`. If the audit finds stale analysis, run `python run_research.py --offline` to apply extraction changes and rebuild analysis and audit from saved downloads. The legacy `human_review_template.csv` is optional and is not a pending step in this workflow. Audit-only runs automatically update the diagnostics ZIP; evidence CSVs containing article excerpts remain local.

All log timestamps and retry deadlines use **UTC**. Vietnam time is UTC+7. **Exit 0 does not establish a complete nine-source study.**

## What to send back

Send:

~~~text
output/diagnostics/latest.zip
~~~

It includes current progress, URL failures, HTTP error history, the last three runs' logs, code/configuration, package versions and run summaries. It excludes the article database, downloaded article bodies, raw files, HTTP cache, environment-variable dumps, credentials and cookies. URLs, local file paths and exception details are included. Very large individual logs are limited to their last 20 MB, with truncation recorded in the bundle manifest.

Every invocation has its own `logs/runs/<UTC timestamp>-<id>/`:

- `events.jsonl`: every request attempt and cache hit, URL, source, purpose, retry number/deadline, HTTP status, duration, byte count, redirects, checkpoints, extraction eligibility/exclusions, errors and tracebacks.
- `console.log`: terminal output, setup output, warnings, phase changes, progress and heartbeats.
- `environment.json`: the pipeline interpreter and dependency versions.
- `summary.json`: final phase results, per-source counts, pending work, holds and exit status.

`logs/latest.json` identifies the newest run. `output/runner_summary.json` is the newest operational summary; `output/run_summary.json` describes the newest published **analysis snapshot**. They may differ after an interrupted or failed update.

Useful optional commands:

~~~powershell
python run_research.py --status
python run_research.py --diagnostics
python run_research.py --verbose
python run_research.py --limit-per-source 25
python run_research.py --offline
python run_research.py --audit-only
python run_research.py --setup-only
python run_research.py --retry-blocked cto travelweekly
~~~

`--status` reads local progress without setup or network requests. `--diagnostics` rebuilds the ZIP without network requests. `--verbose` prints detailed events that are always saved in JSONL anyway. `--limit-per-source 25` limits **article attempts**, not discovery pages. The normal run also walks configured publisher archive pagination for Hospitality Net, WTTC, PATA, AHLA, CTO, Travel Weekly and IH&RA, with a 250-page-per-source invocation bound and saved checkpoints. This supplements sitemap discovery; it does not establish a complete historical inventory. `--offline` skips website collection and updates analysis from local data; first-time environment setup can still require package downloads.

`--setup-only` installs/checks the isolated environment and exits without collecting or changing the corpus. It is useful for checking Python and dependency installation before a long run. You do not need it before the normal command; normal runs perform the same setup automatically.

`--retry-blocked cto travelweekly` rechecks only the named saved holds. For these two user-authorized sources, robots directives are recorded but not applied; collection continues across configured public routes at the normal minimum three-second interval. A 403 on `robots.txt` is treated as unavailable under RFC 9309 §2.3.1.3, and a 403 on an individual sitemap, archive page, or article is recorded and skipped while other URLs continue. A 401 remains a source hold, and 429/rate limits trigger cooldown. The crawler does not disguise its client, use proxies, authenticate, or retry denied URLs. Review publisher terms before redistribution.

## Troubleshooting

| What you see | What to do |
|---|---|
| A long package-installation log on the first run | Let it finish. Packages go into `.venv`, and the package download cache goes into `tmp/pip-cache`. Global Python packages are not changed. |
| Dependency download failure | Check your connection and rerun the same command. Incomplete setup is repaired; a missing project-local pip is bootstrapped again. |
| Heartbeats but no new article counts | Read the current phase: discovery, PDF extraction, deduplication, and models can take time. Detailed events remain in `events.jsonl`. |
| `retry_wait` / `cooldown` | Wait until the saved `next_retry_at` / `until_at` UTC time, then rerun. The program does not contact the source early. |
| HTTP 401/403 on a content URL, a held publisher, or `extraction_error` | For CTO/Travel Weekly, each 403 URL is skipped while other public URLs continue; 401 remains a source hold. For other sources, preserve the hold and review the ZIP. |
| CTO or Travel Weekly has saved old 403 holds | Run `python run_research.py`. The launcher migrates old 403 host holds for these two sources to per-URL skips and resumes the configured public routes slowly. |
| Immediate stop on every run | Check for `data/STOP` or `data/STOP_<source>`. Remove only an intentional stop marker when you want to resume. |
| Disk full, permission error, missing/corrupt database | Keep the files and logs. Free space or resolve the reported filesystem issue; send diagnostics if the database fails its integrity check. Do not delete the corpus to hide the error. |
| The terminal was killed before a ZIP appeared | Run `python run_research.py --diagnostics`, or send the latest folder under `logs/runs/`. |
| Zero eligible articles or a skipped topic model | Check source/date/language coverage and model metadata. The program does not invent themes for an empty or unsuitable corpus. |

To back up the project, stop the runner first and copy the complete `data/` folder, plus `output/`, `logs/`, and the source files. Do not copy only `corpus.sqlite` while a writer is active: SQLite can have committed data in its WAL sidecar. Raw text stays local unless publisher retention/sharing conditions permit otherwise.

## Project structure

~~~text
Tourism-and-Hospitality-Industry-Trends/
  run_research.py              # Public entry point: setup, locking, process logs, diagnostics
  requirements.txt            # Exact tested dependency versions, including transitive packages
  requirements.in             # Direct dependency intent for maintainers
  README.md                   # Start, stop, resume, interpret results, troubleshoot
  RA_FEASIBILITY_PLAN.md       # Original scope and source-access assessment
  docs/
    PROJECT_STRUCTURE.md      # Module map, execution flow, database states, extension guide
    VALIDATION.md             # Verification commands, results and remaining limitations
    AUTOMATED_VALIDATION.md   # Automated audit commands, decision rules and evidence files
    RUN_REVIEW_2026-10-11.md   # Actual-run audit, corrected defects and follow-up work
    CONTENT_QA_2026-10-12.md    # Historical spot-check and codebook corrections
  research/                   # Discovery, HTTP, extraction, analysis, storage and runtime code
  tests/                      # Offline fixtures, recovery tests, numerical model checks
  .venv/                      # Generated isolated Python environment
  data/
    corpus.sqlite             # Private corpus, durable queue, request history and checkpoints
    content_audit_cache.sqlite # Resumable per-record audit decisions and evidence
    raw/                      # Compressed source documents used for extraction QA
    http_cache/               # Cached responses and retrieval metadata
  logs/
    latest.json               # Location of the newest run
    runs/<run-id>/            # Console, JSONL events, environment and final summary
  output/
    PRELIMINARY_REPORT.md      # Last successfully published research report
    QUALITY_CHECKS.json        # Automatically run integrity/arithmetic/archive checks
    runner_summary.json       # Latest operational status
    analysis_state.json       # Publication manifest and artifact hashes
    run_summary.json          # Counts/date for the published analysis snapshot
    tables/                   # CSV research outputs, without full article bodies
    figures/                  # PNG charts
    audit/                    # Completed content audit, evidence, sensitivity and manifest
    diagnostics/latest.zip    # File to send back for debugging/review
    .staging/                 # Analysis work before publication
  tmp/                        # Generated local package/font caches
~~~

The detailed [project structure and maintenance guide](docs/PROJECT_STRUCTURE.md) explains each Python module and database state. Generated data, environment, logs and caches are excluded from Git by `.gitignore`.

## Access and source coverage

- UN Tourism, WTTC and ETC are configured for local public research, with source conditions recorded in `research/config.py`. This does not establish a license to redistribute publisher text.
- PATA, AHLA, Hospitality Net, Travel Weekly, CTO, and IH&RA are enabled for the user's requested research. The user reports authorization for academic collection of publicly accessible material. Any permissions, terms and technical restrictions remain source-specific. The runner honors parseable robots rules generally. For CTO and Travel Weekly only, the user reports the permission supersedes robots directives; those rules are logged but not applied. Rate limits and registered-host checks remain active, 403s are durable per-URL skips, and 401s remain source holds.
- Keep the professor's approval and scope with the project notes, especially any conditions on retention, derived outputs, and sharing full article text.
- IH&RA collection uses press-release, industry-news, and newsroom paths; confirm that resulting records are attributable to the intended association. The CTO and Travel Weekly saved corpus snapshots predate the new URL-local denial behavior; rerun the collector to resume them.
- Download forms are not submitted. Form-only links are inventoried as `form_gated_report`; their downloads are not fetched through hidden form URLs.
- Missing sources and years are reported as coverage gaps, not zero discussion.

Full historical coverage is not certified by processing a sitemap. Removed pages, missing historical archives, uncrawlable pages and restricted full reports can remain absent. The UN archive is paginated to the date boundary; other source inventories currently use their sitemaps, seed archives and linked public PDFs.

The six-source activation and one-time recheck are documented in `research/config.py` and run logs. The user reports that the professor obtained permission for academic crawling. No messages have been sent to publishers or the supervisor.

## Data and analysis outputs

- `data/corpus.sqlite`: URL queue, article text/metadata, request history, source states and checkpoints.
- `data/raw/` and `data/http_cache/`: local compressed downloads and HTTP metadata.
- `output/PRELIMINARY_REPORT.md`: exploratory findings and coverage limitations.
- `output/analysis_state.json`: publication status, input fingerprint and artifact checksums.
- `output/tables/document_metadata.csv`: provenance, dates, language checks, quality flags and exclusions.
- `output/tables/source_coverage.csv` and `coverage_by_source_year.csv`: source/year denominators.
- `output/tables/current_theme_ranking.csv`: current candidate concepts, both article-weighted and equal-source shares.
- `output/tables/themes_by_source_year.csv` and `themes_by_source.csv`: theme shares with denominators.
- `output/tables/discovered_topics_nmf.csv`: TF-IDF/NMF clusters; automated descriptions and source concentration are in `output/audit/nmf_cluster_review.csv`.
- `output/tables/entity_mentions.csv` and `brand_theme_associations.csv`: dictionary mentions and local-context associations.
- `output/tables/sentiment_unvalidated.csv`: optional, unvalidated TextBlob baseline.
- `output/tables/human_review_template.csv`: optional legacy annotation template; not required by the automated workflow.
- `output/audit/FINDINGS.md`: automatically generated interpretation with current themes, website focus, fixed-source historical comparison, brands and limitations.
- `output/audit/`: full-corpus evidence checks, theme focus, source-weighting scenarios, brand contexts and sentiment comparisons.
- `output/figures/`: standalone charts; grey cells indicate no collected observations.
- `output/nmf_model_metadata.json` and `deduplication_metadata.json`: model settings, execution/skip status, and duplicate-search limits.

Primary analysis includes news, blogs and identified press-release PDFs, counting a story at most once per source/year. Report summaries and other report PDFs are separate. Cross-source occurrences remain available for website comparisons. Duplicate pair evidence is exported for review.

The 14-concept rules provide transparent, exploratory mention counts. Their top ten are **candidate themes**, not a calibrated taxonomy. NMF supplies a separate descriptive diagnostic. Brand aliases are a non-exhaustive starter dictionary; co-occurrence does not establish ownership, a formal partnership, reputation or causality. Sentiment reflects publication wording and has no domain accuracy estimate.

The automated audit completes extraction/date checks and contextual evidence review, identifies incidental theme mentions, and reports ranking sensitivity and model disagreement. Use these alongside the exploratory findings; do not present missing historical observations as zero discussion or model agreement as accuracy. See [the audit guide](docs/AUTOMATED_VALIDATION.md) and [original feasibility assessment](RA_FEASIBILITY_PLAN.md).

## Development checks

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
~~~

The tests use simulated HTTP responses and temporary databases. They cover retry deadlines, interrupted writes, cache repair, schema migration, access holds, source locks, diagnostics contents, a small complete pipeline and rerunning it without re-fetching/re-analyzing unchanged data. They do not certify that every publisher's templates remain unchanged or that all historical pages were found.

The runner uses the separate project environment, whose resolved package versions are pinned in `requirements.txt`. It avoids the NumPy/SciPy mismatch in the original global development interpreter. The [validation record](docs/VALIDATION.md) records the environment and checks. Reproducible installation and passing fixtures establish tested behaviour; they do not establish historical completeness or semantic accuracy.

Use the public launcher for real runs. Older individual module entry points exist for development and do not provide all launcher protections.
