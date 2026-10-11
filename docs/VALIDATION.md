# Handoff validation record

This is the original setup record. The [11 October actual-run review](RUN_REVIEW_2026-10-11.md) documents the later full-corpus audit and corrections. The latest expanded offline suite passed **50 tests** on 11 October 2026; machine-readable results are in `tmp/qa/junit.xml`. The original counts below are historical, not current corpus totals.

Verified on **10 October 2026**, Windows x64, Python **3.12.2**, using the project's isolated `.venv`. This record covers software behaviour and setup, not completion of the research study.

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

## Work deliberately left for the normal run

Run the command in the [README](../README.md) to continue the live collection, apply the current extractor to the saved corpus and publish a new analysis snapshot. At handoff, 867 article candidates remained discovered, two legacy fetch failures awaited classification, and 210 report links were form-gated. These are queue counts, not an estimate of all missing historical content.

Existing eligible counts and report files may predate the latest extraction rules; do not present them as final findings. Source access holds, historical coverage reconciliation, independent human validation, theme refinement and review of brand associations remain outstanding. The runner does not claim a complete nine-source census or validated sentiment results.
