# Project structure and maintenance guide

For normal operation, use the [README](../README.md). The supported entry point is `python run_research.py`. Individual research modules are implementation/development entry points; they do not all include the launcher's locking, setup and diagnostic protections.

## Execution flow

```text
run_research.py
  acquire runner lock -> prepare/validate .venv -> start logged child process
    research.run
      acquire pipeline lock -> check database -> recover interrupted URL claims
      for each registered source:
        access check -> resume sitemap/seed discovery
        UN Tourism only: resume English archive pagination
        robots/cooldown check -> resume article/PDF queue
          HTTP cache/network -> raw file -> extraction -> SQLite commit
      changed extractor? -> reprocess existing raw files, one commit per document
      changed inputs/code/dependencies? -> analyze into output/.staging/<run-id>/
      validate artifacts -> publish files -> write complete publication manifest
    child writes operational summary and exits
  launcher packages diagnostic ZIP -> prints paths and exit code -> releases lock
```

Successful document commits survive later failures. Analysis is a separate snapshot; an interrupted update must not be confused with a completed current report. Logs are flushed on every event. Atomic writes plus SQLite transactions protect individual artifacts/records; no design can guarantee preservation of uncommitted work during hardware failure.

## Source-code map

| File | Responsibility |
|---|---|
| [`run_research.py`](../run_research.py) | Parse the user command; build/repair `.venv`; validate dependency imports and compatibility; prevent duplicate runs; capture child stdout/stderr from process start; create diagnostics. |
| [`research/config.py`](../research/config.py) | Fixed study dates, registered source IDs/domains, source classes, access notes, terms URLs, archive routes and candidate-path filters. |
| [`research/run.py`](../research/run.py) | Coordinate phases, collect per-source outcomes, recover the corpus, fingerprint analysis inputs, stage/publish/verify artifacts, summarize completion. |
| [`research/store.py`](../research/store.py) | SQLite schema, additive migrations, URL insertion, audit storage, checkpoints and source states. |
| [`research/http.py`](../research/http.py) | Robots rules, same-host redirect checks, per-source spacing, bounded HTTP retries, Retry-After cooldowns, response cache/checksums and attempt history. |
| [`research/discover.py`](../research/discover.py) | Parse sitemaps and archive seed links. Persist the sitemap frontier after processing each sitemap. |
| [`research/backfill.py`](../research/backfill.py) | Walk UN Tourism's English news archive until every dated item on a page precedes the start boundary; checkpoint each page. |
| [`research/crawl.py`](../research/crawl.py) | Claim eligible queue items, recover interruptions, download/extract documents, save raw files, discover linked public PDFs and preserve form gates. |
| [`research/extract.py`](../research/extract.py) | Source selectors, text cleanup, dates/evidence, language heuristics, HTML/PDF handling and eligibility flags. |
| [`research/reextract.py`](../research/reextract.py) | Apply a changed extractor to saved raw documents without contacting publishers; commit progress per record. |
| [`research/codebook.py`](../research/codebook.py) | Exploratory concept patterns, brand aliases and organization names. |
| [`research/analyze.py`](../research/analyze.py) | Corpus snapshot, duplicate handling, concept shares, brand associations, lexicon sentiment, NMF, review sample, CSVs, report and charts. |
| [`research/runtime.py`](../research/runtime.py) | Atomic file writes, fingerprints, UTC logging, console capture, operating-system locks, heartbeats, stop checks and interruptible waits. |
| [`research/diagnostics.py`](../research/diagnostics.py) | Read-only status snapshots, environment versions, failure listings and an allowlisted diagnostic ZIP. |
| [`research/validate.py`](../research/validate.py) | Read-only audit of a finished corpus: raw/record/artifact integrity, analysis arithmetic, and reconciliation of saved UN archive cards. Writes `output/QUALITY_CHECKS.json`; does not crawl or certify research accuracy. |
| [`research/inspect_samples.py`](../research/inspect_samples.py) | Developer aid for inspecting collected extraction examples. This can display local article text; it is not part of the shareable diagnostic bundle. |
| [`tests/`](../tests) | Offline HTML fixtures, numerical model checks, retry/recovery/migration/cache/lock/log tests and a complete small fixture pipeline. |

## Persistent data

The database is `data/corpus.sqlite`, using SQLite WAL mode. The `-wal` and `-shm` sidecars are normal. For a backup, stop the writer and copy the entire data directory; do not remove sidecars during a run.

| Table | Purpose / key |
|---|---|
| `urls` | Durable queue, keyed by URL. Source/provenance, sitemap last-modified, date/title hints, status, error, attempts, retry deadline, run ID and extraction-code version. |
| `documents` | One extracted document per URL, keyed by stable document ID. Title/body, canonical URL, dates/evidence/confidence, language, content type, quality/exclusion flags, raw path, hash, extractor version and eligibility. |
| `requests` | Append-only attempt history: source, URL, purpose, checked time, status/error, run ID, attempt number, duration, bytes, cache flag and category. A cache hit is attempt `0`. |
| `audit` | Latest structured source-access/discovery audit. Errors and unvisited sitemaps remain visible. |
| `source_state` | Persistent `ready`, `cooldown` or `blocked` state, reason and optional UTC deadline. |
| `fetch_failures` | URL-level failure ledger, retryability and deadline, including failures during discovery. |
| `checkpoints` | Phase/page/frontier status, code/config fingerprint, payload and update time. |

Historical pilot request rows can have empty newer fields. Migrations add fields without inventing missing historical timings or retry counts.

### URL states

| State | Meaning / next step |
|---|---|
| `discovered` | Candidate available for processing. |
| `in_progress` | Claimed by an active worker. Recovered to `discovered` after interruption; already committed documents are reconciled. |
| `extracted` | Extraction was saved. This **does not** mean the article passed English/date/length eligibility checks. |
| `retry_wait` | Transient failure; eligible again after `next_retry_at`. |
| `permanent_error` | Dead URL, robots disallowance, access denial or another non-transient failure; inspect diagnostics. |
| `extraction_error` | Parser/processing exception; URL and traceback logged. Requeued when extraction code changes. |
| `excluded_language_route` | A recognized non-English route excluded before article collection. |
| `form_gated_report` | Report link requires a form; no form submission or hidden-link download is performed. |
| `fetch_or_extract_error` | Legacy pilot status, migrated to an appropriate terminal/pending state on the first runner invocation. |

`documents.eligible` and `exclusion_reason` are separate from queue status. A saved Spanish page, an undated page, or a short archive listing can be `extracted` but ineligible for analysis. Exclusions remain auditable.

### Checkpoint families

- `inventory:<source>`: sitemap/seed discovery attempt finished for its code/config version. A finished inventory attempt can still contain gaps in its audit; it is not a historical completeness certificate.
- `discovery_frontier:<source>`: queued/visited sitemap URLs and accumulated audit information.
- `english_archive:untourism`: next archive page, previous-page signature and date-boundary evidence.
- `analysis`: input fingerprint, running/completed publication state and artifact manifest.

HTML/PDF extraction also has a per-document fingerprint covering extractor/config code and its parsing-library versions. Analysis fingerprints the relevant complete database records, code and dependency versions, so a title/body correction also invalidates the report. Completed work is reused when its inputs and implementation remain valid. Date scope is fixed in `config.py`; moving the computer clock does not silently move the study window.

## Files and publication

- `data/http_cache/<source>/`: URL-hashed compressed responses and JSON metadata. Successful article/discovery responses are reused for this fixed study; cached successful robots responses expire after 24 hours.
- `data/raw/<source>/`: compressed documents keyed by document ID. Used for re-extraction and local quality review.
- `logs/runs/<run-id>/`: `console.log`, `events.jsonl`, environment details and final summary. Run IDs use UTC time plus a random suffix.
- `output/.staging/<run-id>/`: candidate analysis artifacts before publication. Failures here leave the previously published report available.
- `output/analysis_state.json`: written as `publishing` before replacement, then `complete` only after all candidate files are copied. An interrupted publication is rebuilt on the next run. Only files listed in the complete manifest belong to that snapshot; older unlisted files may remain in output folders.
- `output/runner_summary.json`: latest operation, including setup-only/partial/interrupted states. Do not confuse this with `output/run_summary.json`, which belongs to the last published research analysis.
- `output/diagnostics/`: recent run bundles and `latest.zip`. Logs from the last three runs are included, with a 20 MB tail cap per large log. Local article bodies, SQLite and raw/cache directories are excluded.

There is no automatic deletion of old data/logs/staging snapshots. Keep enough disk space, and archive old run folders manually after stopping the runner if needed. Preserve the current database and raw corpus when handing the project between machines.

## Analysis contract

- Main denominators use eligible news, blogs and identified press-release PDFs; report summaries/other report PDFs remain separate.
- Dates must have recorded evidence. Sitemap modification dates are discovery metadata, not publication dates. Missing dates/English verification remain exclusions.
- Exact hashes and high-similarity candidates form story clusters; the primary analysis keeps one occurrence per source/year. Near-duplicate search uses up to six neighbours, so it is not an exhaustive review of every potential pair.
- Candidate concepts are multi-label rule matches. Annual/current shares retain their denominators; a document can discuss multiple concepts.
- NMF runs only with enough documents and usable vocabulary. A skipped model is recorded explicitly in `nmf_model_metadata.json`; missing model output is not replaced with invented topics.
- Sentiment is an unvalidated lexicon baseline. Brand-context co-occurrence is not a verified commercial relationship.
- Human validation, codebook refinement, source coverage reconciliation and final research interpretation remain required.

## Making changes safely

1. Change the relevant module and run `.\.venv\Scripts\python.exe -m pytest -q` from the project root in PowerShell. Tests use temporary databases and fake HTTP; no publisher requests are made.
2. Re-run the normal public command. Changed extractor versions cause local re-extraction. Changed model/codebook inputs invalidate analysis checkpoints. Existing downloaded responses are reused.
3. For source access changes, record the authorization and retention evidence and verify the parser first. Do not disable robots checks or just switch an unvalidated source to enabled.
4. For an HTTP access hold, inspect the failure and current source conditions before changing `source_state`. The normal command deliberately cannot override it.
5. `requirements.in` records direct dependency intent; `requirements.txt` pins the tested complete environment. For dependency changes, resolve the updated direct requirements in a separate temporary environment, test them, and replace the pins with the verified `pip freeze` output. Then run `python run_research.py --setup-only` and the tests in the project `.venv`. Record the resolved versions in the validation record. Do not modify global Python packages or regenerate pins from an unrelated environment.
6. For a new time window, use a separate checkout/data directory. The current crawl queue, publication cache and date filters are designed around the fixed requested window; editing dates alone does not certify a fresh complete inventory.

The test suite establishes runner behaviour on controlled fixtures. It does not establish live archive completeness, current publisher permission or scientific validity of inferred themes.
