# Automated research audit

Status: **completed_with_limitations**. Analysis run: `20261012T025127Z-1439a726`.

This audit runs to completion without human annotation. It audits every saved record and every published theme, entity, association and sentiment row. It reports evidence support, sensitivity and limitations; it does not invent ground-truth accuracy.

## Completed checks

- documents_reviewed: 5,659
- core_articles: 4,829
- theme_assignments_reviewed: 20,524
- entity_rows_reviewed: 6,006
- brand_associations_reviewed: 3,941
- sentiment_rows_compared: 20,524
- nmf_clusters_reviewed: 15
- possible_missing_theme_probes: 224
- focus_supported_assignments: 7,073
- incidental_or_uncertain_assignments: 13,451
- cached_records: 5,659

## Record/date evidence

- visible_date_support: 1,484
- structured_support: 4,082
- unresolved_excluded: 52
- parent_or_archive_support_only: 36
- not_independently_supported: 5

## Automatically applied interpretation

- Use `theme_evidence.csv` and `topic_focus_by_source_year.csv` to distinguish literal mentions from stronger focus evidence. This focus rule is a sensitivity analysis, not a validated classifier.
- Use `current_rank_sensitivity.csv` to compare source balancing, exclusion of sources with fewer than 20 current articles, and every leave-one-source-out scenario.
- `candidate_missing_themes.csv` records alternative lead-text probes. They are retained as uncertainty, not silently counted as confirmed themes.
- `entity_contexts.csv` records literal evidence and career-history contexts. `association_checks.csv` distinguishes same-sentence co-occurrence from weaker window-only matches; neither proves ownership or partnership.
- TextBlob/VADER agreement: 59.55%. `sentiment_comparison.csv` records every agreement, disagreement, and contrast/negation context. Agreement is not accuracy; do not infer industry attitudes.
- `nmf_cluster_review.csv` labels every cluster automatically and quantifies source concentration. These are descriptive lexical groups.
- `coverage_audit.csv` retains every source/year cell, including absent observations and partial boundary years.

## Limitations retained by the completed audit

- Automated evidence/salience tests are heuristic and do not estimate precision or recall.
- Matching saved raw text verifies provenance, not the truth of publisher statements.
- PDF layout and unavailable historical pages are not certified.
- Model agreement is not labelled sentiment accuracy.
- Coverage gaps remain explicitly represented; automated completion is not a nine-source census.

Detailed evidence excerpts are local QA material. The diagnostics ZIP contains only the summary and report, not these text-bearing CSVs.

Method: NLTK VADER documentation: https://www.nltk.org/api/nltk.sentiment.vader.html. The vendored lexicon hash and all thresholds are in summary.json.