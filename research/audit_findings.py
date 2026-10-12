"""Render an evidence-qualified research interpretation from completed audit tables."""
import hashlib
import json
from pathlib import Path

import pandas as pd

from .runtime import atomic_bytes, atomic_json, fingerprint, event


def markdown_table(rows, columns):
    def cell(value):return str(value).replace('|','/').replace('\n',' ')
    return '\n'.join(['| '+' | '.join(columns)+' |', '| '+' | '.join(['---']*len(columns))+' |']+
                     ['| '+' | '.join(cell(row[c]) for c in columns)+' |' for row in rows])


def write_findings(root):
    root=Path(root);output=root/'output';audit=output/'audit'
    state=json.loads((audit/'audit_state.json').read_text('utf-8'))
    summary=json.loads((audit/'summary.json').read_text('utf-8'))
    analysis=json.loads((output/'analysis_state.json').read_text('utf-8'))
    if state['status']!='complete' or not summary['process_complete'] or state['analysis_fingerprint']!=analysis['input_fingerprint']:
        raise RuntimeError('A completed audit of the current analysis is required for findings')
    for name,digest in state['artifacts'].items():
        if hashlib.sha256((audit/name).read_bytes()).hexdigest()!=digest:
            raise RuntimeError('Audit artifact changed before findings: '+name)
    def table(name):return pd.read_csv(output/'tables'/name,keep_default_na=False)
    def evidence(name):return pd.read_csv(audit/name,keep_default_na=False)
    core=table('core_article_metadata.csv');sources=table('source_coverage.csv')
    run=json.loads((output/'run_summary.json').read_text('utf-8'))
    current=core[core.published_at>=run['current_window_start']]
    current_counts=current.groupby('source').size().to_dict()
    source_rows=[]
    for row in sources.to_dict('records'):
        years=sorted(core.loc[core.source==row['source'],'year'].unique())
        source_rows.append({'Source':row['name'],'Saved':row['extracted'],'Core articles':row['core_unique_occurrences'],
                            'Current':current_counts.get(row['source'],0),
                            'Observed years':', '.join(str(y) for y in years) or 'None'})
    mention=evidence('current_rank_sensitivity.csv');focus=evidence('current_focus_rank_sensitivity.csv')
    scenario='equal_source_min20'
    if scenario not in set(focus.scenario):scenario='equal_source_all'
    chosen=focus[focus.scenario==scenario].sort_values('rank').head(10)
    mention_shares=mention[mention.scenario==scenario].set_index('theme').share_pct.to_dict()
    all_ranks=mention[mention.scenario=='equal_source_all'].set_index('theme')['rank'].to_dict()
    article_ranks=mention[mention.scenario=='article_weighted'].set_index('theme')['rank'].to_dict()
    current_rows=[{'Theme':r['theme'],'Focus %':f"{r['share_pct']:.1f}",
                   'Any mention %':f"{mention_shares.get(r['theme'],0):.1f}",
                   'All-source mention rank':all_ranks.get(r['theme'],''),
                   'Article-weighted mention rank':article_ranks.get(r['theme'],'')} for r in chosen.to_dict('records')]
    tags=evidence('theme_evidence.csv');focused=tags[tags.focus_status=='focus_supported']
    profiles=[]
    for source,group in core.groupby('source'):
        counts=focused[focused.source==source].theme.value_counts().head(3)
        profiles.append({'Source':source,'Articles':len(group),
                         'Three leading focus themes':'; '.join(f'{t} ({100*n/len(group):.1f}%)' for t,n in counts.items())})
    # Fixed-source panel avoids presenting changing publisher composition as a
    # temporal change. Both sources have observations throughout this snapshot.
    annual=evidence('topic_focus_by_source_year.csv');panel=['untourism','etc'];annual_rows=[]
    for year,g in annual[annual.source.isin(panel)].groupby('year'):
        present=g.source.nunique()
        if present!=len(panel):continue
        top=g.groupby('theme').focus_share_pct.mean().sort_values(ascending=False).head(3)
        denominators=g.groupby('source').denominator.first()
        annual_rows.append({'Year':year,'Article counts (UN / ETC)':f"{denominators['untourism']} / {denominators['etc']}",
                            'Leading focus themes (equal source weighting)':'; '.join(f'{t} ({v:.1f}%)' for t,v in top.items()),
                            'Caution':'partial year' if year in (2016,2026) else 'small source cell' if denominators.min()<20 else ''})
    brands=table('entity_ranking.csv');brands=brands[brands.entity_type=='brand_name_family'].head(10)
    associations=evidence('association_checks.csv')
    stronger=associations[associations.disposition=='same_sentence_cooccurrence'] if 'disposition' in associations else associations.iloc[:0]
    brand_rows=[]
    for r in brands.to_dict('records'):
        counts=stronger[stronger.brand==r['entity']].theme.value_counts()
        related=f'{counts.index[0]} ({counts.iloc[0]} articles)' if len(counts) else 'No same-sentence association'
        brand_rows.append({'Name family':r['entity'],'Articles mentioning name':r['documents'],'Sources':r['sources'],
                           'Most frequent same-sentence theme':related})
    records=evidence('record_checks.csv')
    findings=[]
    for flag in ['structured_conflict','body_not_well_supported_by_raw_html','raw_headline_disagreement','navigation_or_byline_in_body','pdf_replacement_characters']:
        mask=records['flags'].str.contains(flag,regex=False)
        findings.append({'Flag':flag,'All records':int(mask.sum()),'Eligible records':int((mask & (records.eligible==1)).sum())})
    cluster=evidence('nmf_cluster_review.csv');gaps=evidence('candidate_missing_themes.csv')
    c=summary['counts'];concentrated=int((cluster.dominant_source_share>=.8).sum())
    assoc_counts=associations.disposition.value_counts().to_dict() if 'disposition' in associations else {}
    lines=['# Audited exploratory findings',
        f"\nAnalysis run: `{summary['analysis_run_id']}`. Automated audit: **{summary['status']}**.",
        f"\nThe automated workflow reviewed all **{c['documents_reviewed']:,} saved documents**, including exclusions, and all **{c['theme_assignments_reviewed']:,} theme assignments**, **{c['entity_rows_reviewed']:,} entity rows**, **{c['brand_associations_reviewed']:,} brand/theme rows**, **{c['sentiment_rows_compared']:,} sentiment rows**, and **{c['nmf_clusters_reviewed']} NMF clusters**. No manual annotation step is pending.",
        f"\nThe research sample contains **{len(core):,} core article occurrences**, **{run['report_records']} supplementary report records**, and **{len(current)} current-window articles**. Dates: {run['window_start']} through {run['window_end']}; current: {run['current_window_start']} through {run['window_end']}. These are collected publisher discussions, not a complete industry census.",
        '\n## Source coverage\n',markdown_table(source_rows,['Source','Saved','Core articles','Current','Observed years']),
        '\nCTO and Travel Weekly remain held after HTTP 403 responses. IH&RA records have no eligible core articles. Hospitality Net has only a very small recent sample. Missing years mean no collected observations, not no discussion. Supplementary reports are excluded from the core article denominators.',
        '\n## Ten current themes with stronger focus evidence\n',
        f"This sensitivity view uses **{scenario}** and ranks the mean within-source percentage of articles meeting the disclosed focus rule. With the minimum-20 scenario, sources with fewer than 20 current articles are excluded only from this comparison. The complete original mention ranking remains available in `../tables/current_theme_ranking.csv`. The focus rule is a heuristic, not a calibrated topic classifier. Percentages are multi-label and need not total 100%.",
        '\n'+markdown_table(current_rows,['Theme','Focus %','Any mention %','All-source mention rank','Article-weighted mention rank']),
        f"\nAcross the full corpus, **{c['focus_supported_assignments']:,} / {c['theme_assignments_reviewed']:,}** assignments have stronger focus evidence; **{c['incidental_or_uncertain_assignments']:,}** are incidental or uncertain under this rule. Do not describe every keyword match as a main topic. All weighting and leave-one-source-out results are in `current_rank_sensitivity.csv` and `current_focus_rank_sensitivity.csv`.",
        '\n## Website focus across the collected period\n',markdown_table(profiles,['Source','Articles','Three leading focus themes']),
        '\nEach row uses that website\'s observed period, which differs across publishers. This is a description of collected coverage, not a like-for-like census comparison.',
        '\n## Historical discussion in a fixed-source panel\n',
        'The following panel uses only UN Tourism and ETC in years when both have observations. This holds publisher identity constant; changes in publication selection and small annual samples remain limitations. Both endpoint years are partial. Full per-website/year results are in `topic_focus_by_source_year.csv` and `../tables/themes_by_source_year.csv`.',
        '\n'+markdown_table(annual_rows,['Year','Article counts (UN / ETC)','Leading focus themes (equal source weighting)','Caution']),
        '\n## Brands and associations\n',markdown_table(brand_rows,['Name family','Articles mentioning name','Sources','Most frequent same-sentence theme']),
        f"\nAssociation dispositions: **{assoc_counts.get('same_sentence_cooccurrence',0):,}** same-sentence co-occurrences, **{assoc_counts.get('window_only_weak_evidence',0):,}** window-only matches, and **{assoc_counts.get('career_context_caution',0):,}** career-context cautions. Counts concern literal name families; the dictionary is non-exhaustive and does not map historical corporate ownership. Even same-sentence evidence does not establish a partnership, ownership, reputation or causation. A high count can reflect repeated member announcements.",
        '\n## Sentiment and unsupervised themes\n',
        f"TextBlob and VADER agree on **{summary['sentiment']['agreement_pct']}%** of the theme-context labels. This is model agreement, not accuracy or public opinion. Sentiment remains an optional exploratory diagnostic; disagreement and non-target-specific contexts are recorded individually in `sentiment_comparison.csv`.",
        f"\n**{concentrated} of {len(cluster)} NMF clusters** have at least 80% of assigned articles from one source. Cluster terms can reflect publisher vocabulary, brands and recurring formats as well as topics. The model is descriptive evidence, not an independent validation of the codebook. All labels, concentrations and examples are in `nmf_cluster_review.csv`.",
        '\n## Extraction, dates and coding limits\n',markdown_table(findings,['Flag','All records','Eligible records']),
        '\nRaw-text containment corroborates provenance, not completeness or truth. PDF front-matter checks do not certify layout. Parent-page dates remain explicitly identified. Excluded records and their raw files are retained for reproducibility.',
        f"\nThe alternate headline/lead probes found **{len(gaps)} possible missing theme assignments**. Broad cues such as technology, software, booking or security are candidates rather than accepted labels; some are ambiguous brand names or do not meet the specific codebook definition. `candidate_missing_themes.csv` preserves them. The audit does not estimate semantic precision or recall.",
        '\n## Reproduce and inspect\n',
        'Run `python run_research.py --offline` to apply local corrections, rebuild changed analysis and audit; run `python run_research.py --audit-only` to recheck an already published current snapshot. Both commands resume saved work. `AUDIT_REPORT.md`, `summary.json`, `audit_state.json` and `../QUALITY_CHECKS.json` document completion and evidence. See `../../docs/AUTOMATED_VALIDATION.md` for all decision rules.']
    payload='\n'.join(lines).encode('utf-8')
    atomic_json(audit/'audit_state.json',dict(state,status='publishing'))
    atomic_bytes(audit/'FINDINGS.md',payload)
    state['artifacts']['FINDINGS.md']=hashlib.sha256(payload).hexdigest()
    state['findings_version']=fingerprint(Path(__file__))
    atomic_json(audit/'audit_state.json',state)
    event('audited_findings_published',report=str(audit/'FINDINGS.md'))
    return audit/'FINDINGS.md'
