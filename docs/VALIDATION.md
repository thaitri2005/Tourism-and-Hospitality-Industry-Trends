# Validation and test record

For the current completion status, use the [README status matrix](../README.md#project-status--12-october-2026) and [historical expansion log](HISTORICAL_EXPANSION.md). The normal run `20261012T065126Z-5aec3f63` exited 0 after processing available work and refreshing the audit. The latest published analysis is `20261012T025127Z-1439a726`; the automated audit and structural checks passed for that snapshot. Access and historical coverage remain incomplete, so process success does not mean the nine-source, ten-year research objective is complete.

The full offline suite most recently recorded in `tmp/qa/junit.xml` passed **68 tests, with zero failures or errors**. That test run exercised archive recovery, robots handling, parsing/curation, coding rules, and pipeline behavior. The live rerun validates the operational state and full-corpus audit; it does not by itself test every publisher's site or establish research accuracy. The records below preserve earlier setup and audit history and must not be read as today's corpus totals.

## Earlier full-corpus audit snapshot — superseded

The corrected offline run `20261011T180513Z-d8e94850` finished with exit **0**. The preceding run re-extracted all 5,077 saved documents without errors. The final corpus has **4,525 eligible records, 4,249 core article occurrences, 257 supplementary reports and 545 current-window articles**. All downloads are retained.

- Corrected PATA author/category/navigation contamination and organization boilerplate; excluded four AHLA legal/resource/membership/directory pages. Thirty PATA items fell below the existing article-length threshold after removing non-article material.
- Audited every saved record, **17,778 theme assignments**, **5,340 entity rows**, **2,741 brand/theme rows**, **17,778 sentiment rows** and **15 NMF clusters**. All eight audit consistency checks and all **22 structural checks** passed, with no errors.
- The corrected run reused **5,070** completed record reviews and rechecked changed records/core membership. The fixture test also interrupts an audit after one committed record and verifies that repeating the operation resumes that record without publisher requests.
- Eligible publication dates have 3,186 structured-metadata matches, 1,321 visible-date matches and 18 parent/archive-only matches. No eligible record retained a flagged HTML body/headline mismatch, structured-date conflict, navigation signal or excessive PDF replacement characters. These are evidence-consistency results, not independent verification of publisher claims. The 41 eligible PDFs retain an explicit layout limitation.
- **6,007 of 17,778** theme assignments meet the disclosed stronger-focus heuristic. TextBlob/VADER agreement is **59.89%**, not an accuracy score. Coverage remains six usable sources; blocked and absent source/year cells remain explicit.

`output/audit/FINDINGS.md` is generated automatically from the verified evidence tables and hashed in the audit manifest. The diagnostics bundle includes aggregate findings and audit summaries, while text-bearing evidence CSVs remain local. No human annotation task is pending in this workflow.

The final `--audit-only` run `20261011T181324Z-fad0e127` also exited **0** and reused **all 5,077** cached record reviews. The 35 analysis-artifact hashes and 14 audit-artifact hashes were checked, and the diagnostics ZIP passed CRC, current-artifact and private-evidence exclusion checks. Both final offline/audit runs made **zero publisher requests**.

## Original setup record

Verified on **10 October 2026**, Windows x64, Python **3.12.2**, using the project's isolated `.venv`. The following sections describe the original setup rather than the current research totals.

## Results

| Check | Result |
|---|---|
| Fresh `python run_research.py --setup-only` | Exit 0. Created `.venv`, installed packages, validated imports, wrote logs and a diagnostics ZIP. No publisher crawling or corpus changes. |
| Setup repeated after pinning dependencies | Exit 0. Reused the installed packages; validated imports and dependency consistency again. |
| `.\.venv\Scripts\python.exe -m pip check` | No broken requirements found. |
| `.\.venv\Scripts\python.exe -m pytest -q --junitxml=tmp/qa/junit.xml` | **42 passed, no warnings.** |
| Local status inspection | Existing corpus retained: 615 UN Tourism, 780 WTTC and 561 ETC documents, **1,956 total**. |

The tested dependency versions, including transitive packages, are pinned in [`requirements.txt`](../requirements.txt). Principal versions: NumPy 2.2.6, pandas 3.0.6, SciPy 1.18.1, scikit-learn 1.9.1, Matplotlib 3.11.2, Beautiful Soup 4.15.0, lxml 6.1.3, pypdf 6.20.0 and TextBlob 0.20.1. The pinned SciPy requires Python 3.12+, and the launcher rejects older Python before setup.

Fresh setup logs are retained under `logs/runs/20261010T095654Z-72d79226/`; the pinned-environment recheck is under `logs/runs/20261010T100648Z-299264da/`. The latest test's machine-readable result is `tmp/qa/junit.xml`. Generated logs and QA files are local and excluded from Git.

## What was exercised

- Publication-date evidence, language checks, gated PDFs, article cleanup, theme and entity rules.
- Transient errors, bounded retries, retry deadlines, persistent rate limits/access denials and dead URLs.
- Corrupt cache recovery, interrupted downloads/writes, per-document recovery and schema migration without discarding existing rows.
- Sitemap-frontier and paginated-archive recovery after interruption.
- Operating-system locks across processes and early child-process stderr capture.
- Missing pip, interrupted installation, failed dependency imports and subsequent repair.
- Changed extractor versions, local re-extraction and analysis invalidation after metadata corrections.
- Empty-corpus reporting and preservation of the last report when a new analysis fails.
- Actual NMF fitting on a small, varied numerical fixture, finite exported weights, and explicit skip states for unusable vocabulary.
- A complete small fixture pipeline, followed by the same pipeline again with no further network requests or analysis recomputation.
- Diagnostic ZIP contents excluding the corpus database, raw downloads and fixture article bodies.

The test suite uses fake HTTP responses and temporary databases; it does not contact publishers. The fixture corpus is intentionally small. This is not a load test of an arbitrary ten-year archive.

## Historical handoff note

The earlier queue counts and “work left for the normal run” below this point in prior versions referred to an older corpus snapshot and are superseded by the completed 12 October collection/audit work. Current queue state is in `output/runner_summary.json`; current collection counts and analysis identity are in `output/run_summary.json` and `output/analysis_state.json`. Remaining research limitations are substantive: CTO and Travel Weekly are held after HTTP 403, IH&RA has no eligible in-window core articles, source/year coverage is incomplete, and no labelled gold standard establishes semantic or sentiment accuracy. These are not tasks that a successful rerun can resolve without accessible source material or independent validation.
