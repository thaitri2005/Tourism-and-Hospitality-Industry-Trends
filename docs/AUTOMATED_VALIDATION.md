# Automated validation and audit

## Current result — 12 October 2026

The latest normal invocation, `20261012T065126Z-5aec3f63`, exited 0 with `available_scope_processed`. It found no new accessible article URLs and refreshed the audit for analysis snapshot `20261012T025127Z-1439a726`. The audit reviewed 5,659 documents, 20,524 theme assignments, 6,006 entity rows, 3,941 brand associations, 20,524 sentiment rows and 15 NMF clusters. All eight audit checks passed with zero errors; all 22 structural checks passed. These checks establish workflow and evidence consistency, not representativeness, semantic accuracy or historical completeness. CTO and Travel Weekly remain blocked by HTTP 403; IH&RA has no eligible core articles. The [README status matrix](../README.md#project-status--12-october-2026) and [historical expansion log](HISTORICAL_EXPANSION.md) explain project-level completion.

The required validation workflow is automated. There is no waiting step for a person to fill the historical `human_review_template.csv`. The audit reviews the complete saved corpus and every published assignment, writes its decisions and evidence, and reports specific limits. It does not invent a human gold standard or turn model agreement into an accuracy estimate.

## Commands

From PowerShell in this project:

```powershell
python run_research.py
```

Normal collection and offline rebuilds apply idempotent post-extraction curation rules before analysis, then run the complete audit after publishing analysis. These rules exclude confirmed AHLA directory/membership pages and remove an embedded PATA navigation footer without reparsing unchanged raw files. Each actual correction is logged with its URL, rule, changed fields and before/after word counts. To apply corrections and rebuild everything from existing downloads without contacting publishers:

```powershell
python run_research.py --offline
```

To audit the already published current snapshot only:

```powershell
python run_research.py --audit-only
```

If that audit reports a stale analysis fingerprint, run `--offline` to bring extraction/analysis up to date. Repeat the same command after an interruption. Per-document audit results are cached in `data/content_audit_cache.sqlite`; changed documents, raw bytes or audit rules are rechecked. Completed audit results are staged before publication. Do not delete checkpoints or lock files.

The separate `python -m research.validate` command remains a structural-only check. The complete content audit automatically runs it as well.

## Results and status

Start with `output/audit/FINDINGS.md` for the automatically generated research interpretation: current themes, website focus, a fixed-source historical panel, brands and sentiment limitations. `AUDIT_REPORT.md` and `summary.json` contain the detailed audit status. `audit_state.json` records the exact analysis run, code fingerprints, and hashes of all audit files. `complete` in that manifest plus `completed_with_limitations` in the summary means every scheduled automated review finished and audit/structural consistency checks passed. It does not mean that unavailable websites were collected or that semantic accuracy has been established with labelled ground truth. A `failed` state or errors need investigation; ordinary warnings receive explicit dispositions and do not require a human step to finish the run.

| File under output/audit | What was reviewed |
|---|---|
| FINDINGS.md | Automatically generated research interpretation from verified audit tables. The historical comparison uses a fixed UN Tourism/ETC panel rather than silently changing publisher composition. |
| record_checks.csv | Every saved record, including exclusions: raw-file provenance, HTML text containment, headline consistency, publication-date evidence, archive-date conflicts, English lexical support, navigation signals. PDF checks cover the file and front matter; full layout is not certified. |
| theme_evidence.csv | Every exported theme assignment: literal matched terms, offsets, short evidence context, title/lead hits, sentence support and focus disposition. |
| topic_focus_by_source_year.csv | A stronger-focus alternative alongside the original any-mention rates, with per-source/year denominators. |
| candidate_missing_themes.csv | Alternate domain probes in headlines/leads for missing labels. These are candidates, not automatically accepted truth. |
| current_rank_sensitivity.csv | Article weighting, equal source weighting, sources with at least 20 current articles, and all leave-one-source-out scenarios. |
| current_focus_rank_sensitivity.csv | The same source-weighting tests for stronger-focus assignments. |
| entity_contexts.csv | Every entity mention with literal offsets, local evidence, and career-history flags. |
| association_checks.csv | Every brand/theme pair, distinguishing same-sentence co-occurrence, window-only proximity, and career context. No ownership/partnership is inferred. |
| sentiment_comparison.csv | Every TextBlob theme sentiment row compared with NLTK VADER on the same theme-containing sentences. Records disagreements, negation/contrast and weak topic focus. |
| nmf_cluster_review.csv | Every cluster gets an automated descriptive label, original terms/examples, dominant-source share and concentration warning. |
| coverage_audit.csv | All nine sources across all 11 boundary-inclusive calendar years. Missing observations remain missing; both boundary years are partial. |

## Decision rules and their limits

HTML provenance samples up to 200 evenly spaced five-word sequences from each saved body and looks for them in its raw HTML visible text. Less than 85% support is flagged. This catches unrelated/corrupt body extraction, but cannot prove that the extraction includes all content or that publisher claims are true.

Date evidence distinguishes structured publication metadata, visible article dates, parent/archive dates, conflicting metadata and unresolved dates. Multiple dates are retained; an unrelated date is never silently substituted for a missing publication date. Publication metadata comes from the same publisher, so this is evidence consistency rather than independent fact verification.

A theme has stronger focus evidence when it matches the headline, has at least two matches in the first 100 body words, or has at least three supporting sentences and two distinct terms. Otherwise it remains an incidental-or-uncertain mention. This rule is disclosed as sensitivity analysis, not a calibrated classifier. General-topic probes are also disclosed and are never silently merged into the original codebook labels.

VADER uses a vendored, hash-pinned lexicon; installation on a new computer does not need a model/API download. TextBlob and VADER are different lexical methods. Their agreement is a diagnostic, not precision/recall, human inter-rater agreement, or sentiment toward a particular brand/theme. The audit retains the original optional sentiment output and marks model disagreement and weak target relevance.

NMF labels are descriptions of model terms. A dominant-source share of 80% or more is highlighted; concentration alone does not prove a cluster is invalid. Source identity and recurring formats can still explain clusters even after common publisher tokens are removed.

## Recovery, logging and privacy

The launcher provides locks, 30-second heartbeats and a diagnostics ZIP for audit-only runs as well. Detailed progress logs record every 200 records, cache reuse, failures and final counts. The raw corpus and audit-cache data are local. Evidence CSVs contain short original-text contexts, so they are excluded from the shareable diagnostics ZIP. The ZIP includes the audit summary, report, manifest and implementation/resource files. The professor-reported permission and its scope govern any distribution of article text.

The automated process can finish with known limits: blocked publishers, absent historical pages, domain/model ambiguity and PDF layout uncertainty. These are retained in the report rather than converted into fabricated validation scores.
## Archive expansion follow-up

The 2026-10-12 follow-up adds checkpointed publisher archive pagination, wildcard robots checks, Hospitality Net main-content cleanup, and codebook 0.6. See [HISTORICAL_EXPANSION.md](HISTORICAL_EXPANSION.md) for the evidence and [the 323-row coding review](CODING_REVIEW_2026-10-12.csv) for prior omission dispositions. A larger current sample does not establish historical completeness. The 12 October 2026 collection/rebuild is complete. Its automated audit reviewed 5,659 saved documents, and all audit consistency checks passed; see `output/audit/summary.json` and `docs/HISTORICAL_EXPANSION.md` for the exact run and limitations.

