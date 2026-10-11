# Tourism and hospitality industry discourse research

An executable first attempt at Jenny Le's RA brief: English material from **10 October 2016 through 10 October 2026**, from the nine supplied sources. The brief says ten websites but lists nine; Global Brands Magazine is a brand-reference lead, not a tenth corpus source. Both endpoint calendar years are partial. “Current” means 11 October 2025 through 10 October 2026.

This studies publisher discussion, not consumer or whole-industry opinion. Existing pilot data is retained. Old report files may describe an earlier snapshot: check `output/runner_summary.json` and `output/analysis_state.json` before using them.

The completed run was reviewed on 11 October 2026. See [the run review](docs/RUN_REVIEW_2026-10-11.md) for confirmed defects, fixes, and remaining research gaps. The follow-up run **recovered all 62 previously missed UN Tourism article links**, adding 61 eligible articles. The verified snapshot now contains **2,886 saved documents and 2,224 core articles**, with no pending candidates. No further crawl is needed for that recovery; the next work is manual validation and resolution of missing-source access and historical coverage. The normal command below remains the supported way to resume future work.

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
4. Send `output/diagnostics/latest.zip` back to the assistant for review. If the run stops with errors, send the ZIP anyway.
5. Open `output/PRELIMINARY_REPORT.md` for the research summary and `output/tables/` for CSVs, but check the completion indicators below first.

**Run exactly the same command after an interruption or temporary failure.** Do not delete the database, cache, checkpoints, lock files, or `.venv` to restart. This reuses work already saved; it does not start the corpus over.

If Windows says `python` is not recognized, try `py -3.12 --version`, then use `py -3.12 run_research.py` consistently. If neither Python command works, install Python 3.12 with its command-line launcher first. If this project is in another folder, replace the path in `Set-Location`.

## What the command does

The launcher:

1. Creates `.venv` and installs/checks dependencies inside it. Setup output is logged; an interrupted installation is retried on the next invocation.
2. Acquires an operating-system lock, checks SQLite, and recovers interrupted items.
3. Resumes sitemap discovery and the English UN Tourism archive walk. Successful discovery responses are cached; the archive page and sitemap frontier are checkpointed.
4. Collects permitted candidate articles and directly linked public PDFs. Each document commits separately. Successful URLs are skipped; incomplete downloads or cache mismatches are recovered.
5. Re-extracts saved documents only when the extractor changes, using local raw files.
6. Builds the preliminary analysis, tables and charts. It stages the entire analysis before publishing files; unchanged, verified output is reused.
7. Writes a status summary and a shareable diagnostics ZIP, including when ordinary errors or Ctrl+C occur.

Sources run sequentially with at least 1.1 seconds between requests, or a longer robots crawl delay. Request reads time out after 35 seconds. Body size is capped at 30 MB. Runtime depends on archive sizes, publisher responses and analysis time. Keep the terminal open; a heartbeat appears every 30 seconds during long phases.

## Stop and resume

Press **Ctrl+C once** and allow the process to finish writing its summary. Then run `python run_research.py` again. Closing the terminal or a hard crash can prevent final diagnostics, but committed documents and checkpoints survive; the next invocation recovers unfinished work. Logs are flushed on every event. A second lock protects against an orphaned child process if only its launcher was killed.

Alternatively, create `data/STOP`, or `data/STOP_untourism` for one source. Remove that marker yourself when ready to resume. The program does not silently remove intentional stop files.

An active second copy exits instead of collecting concurrently. Lock files may remain after exit; their presence does not mean a process still owns the OS lock. **Do not delete them.**

## Retry behaviour

| Situation | Automatic handling |
|---|---|
| Timeout, connection reset, HTTP 408/425/500/502/503/504 | At most three HTTP attempts for that fetch, with exponential backoff and jitter. After exhaustion, save a retry deadline at least five minutes ahead. |
| HTTP 429 or a transient response with `Retry-After` | Persist a source cooldown; never retry earlier than the server's deadline. Other sources can continue. |
| Rerun before a retry deadline | Keep the item pending and report the UTC deadline. Do not contact it early. Run the same command again after the deadline. |
| Five consecutive document failures | Pause that source for at least five minutes and continue with other sources. |
| HTTP 401/403 | Persist an access hold for the source. No automatic bypass or repeated access probing. |
| HTTP 404/410 or another permanent URL failure | Record it for review; do not retry it endlessly. |
| Extraction exception | Log the URL and full traceback. Retry automatically when the extractor code changes. |
| Changed extraction rules | Reprocess local raw documents with per-document checkpoints. |
| Corrupt/incomplete HTTP cache | Log the defect and fetch a fresh response when access permits. |
| Interrupted analysis/publication | Preserve the previous completed report where possible; verify the publication manifest and rebuild on the next invocation. |

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
- `study_complete`: deliberately `false`; full source coverage and independent human validation are not established by this software.

Only treat the output file set as a successful publication when `output/analysis_state.json` has `status: "complete"`. Its artifact hashes are verified on the next run. If an update fails, older report files can still exist; their snapshot date is in `output/run_summary.json`. A setup-only run deliberately reports `analysis_current: false` and leaves prior research outputs untouched.

### Check the finished results locally

After the runner exits, use this optional audit command from the project folder:

~~~powershell
.\.venv\Scripts\python.exe -m research.validate
~~~

It reads the database and saved files without contacting websites. It checks raw-file readability, record hashes, eligibility constraints, report hashes/freshness, exported counts, theme percentages, brand association arithmetic, sentiment/NMF alignment, and saved UN archive links against the URL inventory. It writes `output/QUALITY_CHECKS.json`. Exit `0` means these structural checks passed; exit `1` means at least one failed. Coverage warnings remain separate from structural failures. Neither result certifies research accuracy or complete historical coverage. Run it again after each new collection; the audit identifies the analysis run it checked.

To include the latest audit in the shareable diagnostic ZIP, run `python run_research.py --diagnostics` afterward. For substantive validation, copy `output/tables/human_review_template.csv` somewhere outside `output/` before filling it in: analysis regenerates that template. Review the linked original articles for date, text extraction, topic coding, and entity matches. Blank reviewer fields are not completed validation.

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
python run_research.py --setup-only
~~~

`--status` reads local progress without setup or network requests. `--diagnostics` rebuilds the ZIP without network requests. `--verbose` prints detailed events that are always saved in JSONL anyway. `--limit-per-source 25` limits **article attempts**, not discovery pages. `--offline` skips website collection and updates analysis from local data; first-time environment setup can still require package downloads.

`--setup-only` installs/checks the isolated environment and exits without collecting or changing the corpus. It is useful for checking Python and dependency installation before a long run. You do not need it before the normal command; normal runs perform the same setup automatically.

## Troubleshooting

| What you see | What to do |
|---|---|
| A long package-installation log on the first run | Let it finish. Packages go into `.venv`, and the package download cache goes into `tmp/pip-cache`. Global Python packages are not changed. |
| Dependency download failure | Check your connection and rerun the same command. Incomplete setup is repaired; a missing project-local pip is bootstrapped again. |
| Heartbeats but no new article counts | Read the current phase: discovery, PDF extraction, deduplication, and models can take time. Detailed events remain in `events.jsonl`. |
| `retry_wait` / `cooldown` | Wait until the saved `next_retry_at` / `until_at` UTC time, then rerun. The program does not contact the source early. |
| HTTP 401/403, a held publisher, or `extraction_error` | Send the ZIP for review. Repeating the command does not override access restrictions or fix parser code. |
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
    RUN_REVIEW_2026-10-11.md   # Actual-run audit, corrected defects and follow-up work
  research/                   # Discovery, HTTP, extraction, analysis, storage and runtime code
  tests/                      # Offline fixtures, recovery tests, numerical model checks
  .venv/                      # Generated isolated Python environment
  data/
    corpus.sqlite             # Private corpus, durable queue, request history and checkpoints
    raw/                      # Compressed source documents used for extraction QA
    http_cache/               # Cached responses and retrieval metadata
  logs/
    latest.json               # Location of the newest run
    runs/<run-id>/            # Console, JSONL events, environment and final summary
  output/
    PRELIMINARY_REPORT.md      # Last successfully published research report
    QUALITY_CHECKS.json        # Optional local integrity/arithmetic/archive audit
    runner_summary.json       # Latest operational status
    analysis_state.json       # Publication manifest and artifact hashes
    run_summary.json          # Counts/date for the published analysis snapshot
    tables/                   # CSV research outputs, without full article bodies
    figures/                  # PNG charts
    diagnostics/latest.zip    # File to send back for debugging/review
    .staging/                 # Analysis work before publication
  tmp/                        # Generated local package/font caches
~~~

The detailed [project structure and maintenance guide](docs/PROJECT_STRUCTURE.md) explains each Python module and database state. Generated data, environment, logs and caches are excluded from Git by `.gitignore`.

## Access and source coverage

- UN Tourism, WTTC and ETC are configured for local public research, with source conditions recorded in `research/config.py`. This does not establish a license to redistribute publisher text.
- PATA, AHLA, Hospitality Net and Travel Weekly remain disabled because the inspected terms restrict automated collection. They require documented publisher authorization or an appropriately licensed export. Robots permission does not override terms.
- CTO returned HTTP 403 on its robots request in the pilot audit; this denial is retained as an access hold.
- The supplied IH&RA site needs verification because old association content is mixed with extensive hotel listings.
- Download forms are not submitted. Form-only links are inventoried as `form_gated_report`; their downloads are not fetched through hidden form URLs.
- Missing sources and years are reported as coverage gaps, not zero discussion.

Full historical coverage is not certified by processing a sitemap. Removed pages, missing historical archives, uncrawlable pages and restricted full reports can remain absent. The UN archive is paginated to the date boundary; other source inventories currently use their sitemaps, seed archives and linked public PDFs.

To add approved access, record the permission/retention evidence and implement or verify the source's extraction adapter. Do not just flip a configuration flag. Existing selectors are not validated for disabled sources. No messages have been sent to publishers or the supervisor.

## Data and analysis outputs

- `data/corpus.sqlite`: URL queue, article text/metadata, request history, source states and checkpoints.
- `data/raw/` and `data/http_cache/`: local compressed downloads and HTTP metadata.
- `output/PRELIMINARY_REPORT.md`: exploratory findings and coverage limitations.
- `output/analysis_state.json`: publication status, input fingerprint and artifact checksums.
- `output/tables/document_metadata.csv`: provenance, dates, language checks, quality flags and exclusions.
- `output/tables/source_coverage.csv` and `coverage_by_source_year.csv`: source/year denominators.
- `output/tables/current_theme_ranking.csv`: current candidate concepts, both article-weighted and equal-source shares.
- `output/tables/themes_by_source_year.csv` and `themes_by_source.csv`: theme shares with denominators.
- `output/tables/discovered_topics_nmf.csv`: independent TF-IDF/NMF clusters for human interpretation.
- `output/tables/entity_mentions.csv` and `brand_theme_associations.csv`: dictionary mentions and local-context associations.
- `output/tables/sentiment_unvalidated.csv`: optional, unvalidated TextBlob baseline.
- `output/tables/human_review_template.csv`: a sample awaiting human coding.
- `output/figures/`: standalone charts; grey cells indicate no collected observations.
- `output/nmf_model_metadata.json` and `deduplication_metadata.json`: model settings, execution/skip status, and duplicate-search limits.

Primary analysis includes news, blogs and identified press-release PDFs, counting a story at most once per source/year. Report summaries and other report PDFs are separate. Cross-source occurrences remain available for website comparisons. Duplicate pair evidence is exported for review.

The 14-concept rules provide transparent, exploratory mention counts. Their top ten are **candidate themes**, not a validated taxonomy. NMF supplies an independent discovery check, not automatic ground truth. Brand aliases are a non-exhaustive starter dictionary; co-occurrence does not establish ownership, a formal partnership, reputation or causality. Sentiment reflects publication wording and has no domain accuracy estimate.

Review extraction/date quality, label a held-out human sample, refine themes and verify brand associations before reporting final research findings. See [the original feasibility assessment](RA_FEASIBILITY_PLAN.md) for scope and source evidence.

## Development checks

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
~~~

The tests use simulated HTTP responses and temporary databases. They cover retry deadlines, interrupted writes, cache repair, schema migration, access holds, source locks, diagnostics contents, a small complete pipeline and rerunning it without re-fetching/re-analyzing unchanged data. They do not certify that every publisher's templates remain unchanged or that all historical pages were found.

The runner uses the separate project environment, whose resolved package versions are pinned in `requirements.txt`. It avoids the NumPy/SciPy mismatch in the original global development interpreter. The [validation record](docs/VALIDATION.md) records the environment and checks used for this handoff. Reproducible installation and passing fixtures do not establish source completeness or replace human research validation.

Use the public launcher for real runs. Older individual module entry points exist for development and do not provide all launcher protections.
