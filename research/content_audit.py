"""Resumable automated content/evidence audit; no network or human labels required.

This checks every saved record and every exported assignment. Evidence support,
topic focus and model agreement are diagnostics, not calibrated accuracy scores.
"""
import csv
import gzip
import hashlib
import io
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from dateutil.parser import parse as date_parse
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import pandas as pd
import nltk.data
from pypdf import PdfReader

from .config import ROOT, SOURCES, START, END
from .codebook import THEMES, tag_themes, entity_patterns, entity_matches
from .runtime import atomic_bytes, atomic_json, check_stop, event, fingerprint, RunLock, heartbeat
from .store import now

RESOURCE = Path(__file__).parent/'resources/vader_lexicon.txt'
EXPECTED_LEXICON = '0aabac74cd95def2dbedc04ce55e39698d91113ffadb6d86b87dd337c4d2184d'
SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z“\"])')
VISIBLE_DATE = re.compile(r'\b(?:\d{1,2}(?:st|nd|rd|th)?\s+[A-Z][a-z]{2,8}\s*,?\s*20\d{2}|[A-Z][a-z]{2,8}\s+\d{1,2}(?:st|nd|rd|th)?\s*,?\s*20\d{2}|\d{1,2}\.\d{1,2}\.20\d{2})\b')
PROBES = {
    'Demand, performance and recovery': r'\b(?:bookings?|travel intentions?|tourism demand|hotel demand|travel sentiment|visitor growth)\b',
    'AI and digital technology': r'\b(?:biometric\w*|digital tools?|software|technology|smart hotels?|digital identity)\b',
    'Workforce, skills and education': r'\b(?:recruitment|staffing|employees?|workers?|labour|labor|wages)\b',
    'Distribution, booking and business models': r'\b(?:vacation rental|business model|reservation system|distribution platform|subscription)\b',
    'Health, safety and crisis resilience': r'\b(?:security|vaccination|cleaning standards|infection|safety protocols)\b',
    'Sustainability, climate and nature': r'\b(?:ecotourism|waste reduction|renewable energy|conservation)\b',
}


def normalized(value):
    return ' '.join(re.findall(r'\w+', value.casefold()))


def parsed_date(value):
    value=str(value or '')
    if not re.search(r'\b(?:19|20)\d{2}\b',value): return ''
    try:
        return date_parse(value,default=datetime(1900,1,1),dayfirst=bool(re.match(r'^\d{1,2}\.\d{1,2}\.',value))).date().isoformat()
    except (ValueError,TypeError,OverflowError): return ''


def date_values(value):
    if isinstance(value,dict):
        kinds=value.get('@type',[])
        if isinstance(kinds,str): kinds=[kinds]
        if any(k in ('Article','NewsArticle','BlogPosting','Report') for k in kinds):
            if value.get('datePublished'): yield value['datePublished']
        for child in value.values(): yield from date_values(child)
    elif isinstance(value,list):
        for child in value: yield from date_values(child)


def containment(body, visible):
    """Fraction of up to 200 evenly spaced body five-grams in raw visible text."""
    words=normalized(body).split(); raw=normalized(visible)
    if len(words)<5: return float(normalized(body) in raw)
    count=len(words)-4
    positions=sorted({int(i*(count-1)/max(min(200,count)-1,1)) for i in range(min(200,count))})
    return sum(' '.join(words[i:i+5]) in raw for i in positions)/len(positions)


def raw_review(doc, data, hint):
    notes=[]; dates=[]; visible_dates=[]; support=None; match_ratio=None
    is_pdf=data.startswith(b'%PDF')
    if is_pdf:
        reader=PdfReader(io.BytesIO(data))
        # HTML body checks use raw visible text; PDF layout is explicitly limited.
        front=' '.join((p.extract_text() or '') for p in list(reader.pages)[:2])
        visible_dates=[parsed_date(m.group()) for m in VISIBLE_DATE.finditer(front[:8000])]
        notes.append('pdf_layout_not_certified')
        if doc['body'].count('\ufffd')/max(len(doc['body']),1)>.005: notes.append('pdf_replacement_characters')
    else:
        soup=BeautifulSoup(data,'lxml')
        for n in soup.select('meta[property="article:published_time"], meta[name="datePublished"]'):
            dates.append(parsed_date(n.get('content')))
        for n in soup.select('script[type="application/ld+json"]'):
            try: dates.extend(parsed_date(x) for x in date_values(json.loads(n.get_text())))
            except (ValueError,TypeError): pass
        for n in soup.select('.field--field-published time[datetime]'):
            dates.append(parsed_date(n.get('datetime')))
        # Examine article/header dates only; whole-page dates include unrelated cards.
        region=soup.select_one('.blog-item-content.e-content, .details-block, .node__content, article, main') or soup
        visible_dates=[parsed_date(m.group()) for m in VISIBLE_DATE.finditer(region.get_text(' ',strip=True)[:2200])]
        title=soup.find('h1')
        if title:
            a=set(normalized(doc['title']).split()); b=set(normalized(title.get_text(' ',strip=True)).split())
            match_ratio=len(a&b)/max(len(a),1)
            if match_ratio<.7: notes.append('raw_headline_disagreement')
        for n in soup.select('script,style,noscript'): n.decompose()
        support=containment(doc['body'],soup.get_text(' ',strip=True))
        if support<.85: notes.append('body_not_well_supported_by_raw_html')
    dates=sorted(set(filter(None,dates))); visible_dates=sorted(set(filter(None,visible_dates)))
    published=doc.get('published_at') or ''
    hint_date=hint.get('hint_date') or ''
    if dates:
        date_status='structured_support' if published in dates else 'structured_conflict'
        if len(dates)>1: notes.append('multiple_structured_publication_dates')
    elif published and published in visible_dates: date_status='visible_date_support'
    elif published and hint_date==published: date_status='parent_or_archive_support_only'
    elif not published: date_status='unresolved_excluded' if not doc['eligible'] else 'missing_date_in_core'
    else: date_status='not_independently_supported'
    if hint_date and published and hint_date!=published: notes.append('archive_date_disagreement')
    if date_status in ('structured_conflict','missing_date_in_core'): notes.append(date_status)
    if published and parsed_date(published)!=published: notes.append('invalid_publication_date')
    words=re.findall('[a-z]+',doc['body'].lower())
    function_count=sum(w in {'the','and','of','to','in','is','for','that','with','as','on','was','are','by','from','at','be','it'} for w in words)
    ratio=function_count/max(len(words),1)
    if doc['eligible'] and ratio<.06: notes.append('weak_english_lexical_support')
    if re.search(r'\n(?:Written By|Previous|Next|Back to Blog Homepage >)\s*\n',doc['body']): notes.append('navigation_or_byline_in_body')
    return dict(doc_id=doc['doc_id'],source=doc['source'],url=doc['url'],published_at=published,
        eligible=int(doc['eligible']),exclusion_reason=doc['exclusion_reason'] or '',date_check=date_status,
        structured_dates=';'.join(dates),opening_visible_dates=';'.join(visible_dates),archive_date=hint_date,
        raw_body_support=round(support,4) if support is not None else '',raw_headline_support=match_ratio if match_ratio is not None else '',
        english_function_word_share=round(ratio,4),raw_sha256=hashlib.sha256(data).hexdigest(),
        check_scope='pdf_header_and_front_matter' if is_pdf else 'html_date_headline_body',
        flags=';'.join(notes),disposition='retained_with_cautions' if doc['eligible'] and notes else ('retained' if doc['eligible'] else 'excluded_by_eligibility'))


def polarity_label(values,threshold):
    pos=any(x>threshold for x in values); neg=any(x < -threshold for x in values)
    return 'mixed' if pos and neg else 'positive' if pos else 'negative' if neg else 'neutral'


def semantic_review(doc, vader):
    # Different focus and sentiment checks alongside the original mention rules.
    title=' '.join(doc['title'].split()); body=' '.join(doc['body'].split())
    text=body if title.casefold() in body.casefold() else title+'. '+body
    lead=' '.join(body.split()[:100]); titles=tag_themes(title); leads=tag_themes(lead)
    tagged=tag_themes(text); sentences=SENTENCE_SPLIT.split(text)
    sentence_tags=[tag_themes(s) for s in sentences]
    sentiment_scores=[vader.polarity_scores(s)['compound'] if tags else 0 for s,tags in zip(sentences,sentence_tags)]
    themes=[]; sentiments=[]; gaps=[]
    for theme,hits in tagged.items():
        ids=[i for i,tags in enumerate(sentence_tags) if theme in tags]
        terms=sorted({m.group().lower() for m in hits})
        focus=bool(theme in titles or len(leads.get(theme,[]))>=2 or (len(ids)>=3 and len(terms)>=2))
        scores=[sentiment_scores[i] for i in ids]
        confidence='focus_supported' if focus else 'incidental_or_uncertain'
        themes.append(dict(doc_id=doc['doc_id'],source=doc['source'],year=doc['published_at'][:4],theme=theme,
            matched_terms='; '.join(terms),match_count=len(hits),title_hits=len(titles.get(theme,[])),lead_hits=len(leads.get(theme,[])),
            supporting_sentences=len(ids),sentence_share=round(len(ids)/max(len(sentences),1),4),
            focus_status=confidence,evidence_start=hits[0].start(),evidence_end=hits[0].end(),
            evidence_excerpt=text[max(0,hits[0].start()-70):hits[0].end()+100],url=doc['url']))
        risky=sum(bool(re.search(r'\b(?:not|never|no|despite|however|but|although)\b',sentences[i],re.I)) for i in ids)
        sentiments.append(dict(doc_id=doc['doc_id'],theme=theme,vader_label=polarity_label(scores,.05),
            vader_mean=round(sum(scores)/max(len(scores),1),4),context_sentences=len(ids),
            negation_or_contrast_sentences=risky,focus_status=confidence))
    for theme,probe in PROBES.items():
        m=re.search(probe,title+' '+lead,re.I)
        if m and theme not in tagged:
            gaps.append(dict(doc_id=doc['doc_id'],source=doc['source'],theme=theme,lead_probe=m.group(),
                disposition='candidate_missing_theme_not_automatically_accepted',url=doc['url']))
    entities=[]; associations=[]
    for name,kind,pattern in entity_patterns():
        matches=entity_matches(name,pattern,text)
        if not matches: continue
        positions=[m.start() for m in matches]; nearby=defaultdict(list)
        for m in matches:
            context=text[max(0,m.start()-350):m.end()+350]
            for theme in tag_themes(context): nearby[theme].append(context)
        contexts=[text[max(0,m.start()-160):m.end()+160] for m in matches]
        employment=any(re.search(r'\b(?:previously|formerly|experience from|prior (?:roles?|experience)|career at)\b',s,re.I) for s in contexts)
        entities.append(dict(doc_id=doc['doc_id'],entity=name,entity_type=kind,mentions=len(matches),source=doc['source'],
            offsets=';'.join(map(str,positions)),context_type='career_history_present' if employment else 'ordinary_mention',
            evidence_excerpt=contexts[0],url=doc['url']))
        if kind=='brand_name_family':
            for theme in nearby:
                same_sentence=any(theme in tags and entity_matches(name,pattern,s) for s,tags in zip(sentences,sentence_tags))
                associations.append(dict(doc_id=doc['doc_id'],brand=name,theme=theme,source=doc['source'],
                    same_sentence=same_sentence,career_history_present=employment,
                    disposition='career_context_caution' if employment else 'same_sentence_cooccurrence' if same_sentence else 'window_only_weak_evidence'))
    return dict(themes=themes,sentiments=sentiments,entities=entities,associations=associations,gaps=gaps)


def frame(rows,columns):
    return pd.DataFrame(rows,columns=columns if not rows else None)


def write_table(stage,name,rows,columns):
    df=rows if isinstance(rows,pd.DataFrame) else frame(rows,columns)
    atomic_bytes(stage/name,df.to_csv(index=False).encode('utf-8-sig'))
    return df


def rank_scenarios(core,tags,current_start):
    cur=core[core.published_at>=current_start]; counts=cur.groupby('source').size().to_dict()
    current=tags[tags.doc_id.isin(cur.doc_id)]
    names=sorted(THEMES); nums=current.groupby(['source','theme']).size().to_dict()
    sets={'equal_source_all':list(counts),'equal_source_min20':[s for s,n in counts.items() if n>=20]}
    sets.update({'omit_'+s:[v for v in counts if v!=s] for s in counts})
    result=[]
    for scenario,active in sets.items():
        if not active: continue
        rows=[dict(scenario=scenario,theme=t,share_pct=sum(100*nums.get((s,t),0)/counts[s] for s in active)/len(active),
                   sources=';'.join(active),denominator=sum(counts[s] for s in active)) for t in names]
        rows.sort(key=lambda r:(-r['share_pct'],r['theme']))
        for i,r in enumerate(rows,1):r['rank']=i;result.append(r)
    rows=[dict(scenario='article_weighted',theme=t,share_pct=100*sum(nums.get((s,t),0) for s in counts)/max(len(cur),1),
               sources=';'.join(counts),denominator=len(cur)) for t in names]
    rows.sort(key=lambda r:(-r['share_pct'],r['theme']))
    for i,r in enumerate(rows,1):r['rank']=i;result.append(r)
    return result


def cluster_label(terms):
    for label,pattern in [
        ('Publisher language / PATA',r'\bpata\b'),('Publisher language / AHLA',r'\bahla\b'),
        ('Brand / Sabre distribution technology',r'\bsabre\b'),('Brand / Dusit hotels',r'\bdusit\b'),
        ('Health and crisis response',r'covid|pandemic|protocols'),('Cultural heritage and awards',r'heritage|cultural routes'),
        ('Employment and staffing',r'staffing|wages|workers'),('Long-haul travel intentions',r'long-haul|barometer'),
        ('Economic contribution and spending',r'\bgdp\b|visitor spending|economic impact'),
        ('Tourism demand and arrivals',r'arrivals|demand'),('Institutional events and summits',r'summit'),
        ('European travel intentions',r'europeans|respondents'),('Training and capacity building',r'training|course'),
        ('Development and institutional discourse',r'development|secretary-general')]:
        if re.search(pattern,terms): return label
    return 'Mixed lexical cluster: '+ '; '.join(terms.split('; ')[:3])


def run_audit(root=ROOT):
    root=Path(root); output=root/'output'; destination=output/'audit'; destination.mkdir(exist_ok=True)
    manifest=json.loads((output/'analysis_state.json').read_text('utf-8'))
    if manifest.get('status')!='complete':raise RuntimeError('Complete analysis required before audit')
    lexicon_hash=hashlib.sha256(RESOURCE.read_bytes()).hexdigest()
    if lexicon_hash!=EXPECTED_LEXICON:raise RuntimeError('VADER lexicon hash differs from pinned resource')
    resource_root=str(RESOURCE.parent)
    if resource_root not in nltk.data.path:nltk.data.path.insert(0,resource_root)
    vader=SentimentIntensityAnalyzer(lexicon_file=RESOURCE.name)
    version=fingerprint(Path(__file__),Path(__file__).parent/'codebook.py',extra=lexicon_hash)
    stage=destination/'.staging';stage.mkdir(exist_ok=True)
    # Prior outputs remain intact until this run can publish an entire file set.
    atomic_json(destination/'audit_state.json',dict(status='running',analysis_run_id=manifest.get('run_id'),audit_version=version))
    cache=sqlite3.connect(root/'data/content_audit_cache.sqlite')
    cache.execute('CREATE TABLE IF NOT EXISTS reviews (doc_id TEXT PRIMARY KEY, fingerprint TEXT, payload TEXT)')
    db=sqlite3.connect((root/'data/corpus.sqlite').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;db.execute('BEGIN')
    docs=[dict(r) for r in db.execute('SELECT * FROM documents ORDER BY doc_id')]
    hints={r['url']:dict(r) for r in db.execute('SELECT * FROM urls')};db.close()
    def table(name):return pd.read_csv(output/'tables'/name,keep_default_na=False)
    core=table('core_article_metadata.csv'); core_ids=set(core.doc_id); tags=table('theme_assignments.csv')
    checks=[]; themes=[]; sentiments=[]; entities=[]; associations=[]; gaps=[]; errors=[]; reused=0
    try:
        for i,doc in enumerate(docs):
            check_stop(root/'data')
            try:
                compressed=(root/doc['raw_path']).read_bytes()
                signature=hashlib.sha256((version+json.dumps(doc,sort_keys=True)+str(doc['doc_id'] in core_ids)+
                    str(hints.get(doc['url'],{}).get('hint_date'))).encode()+compressed).hexdigest()
                previous=cache.execute('SELECT payload FROM reviews WHERE doc_id=? AND fingerprint=?',(doc['doc_id'],signature)).fetchone()
                if previous:review=json.loads(previous[0]);reused+=1
                else:
                    review=dict(record=raw_review(doc,gzip.decompress(compressed),hints.get(doc['url'],{})))
                    if doc['doc_id'] in core_ids:review.update(semantic_review(doc,vader))
                    cache.execute('INSERT OR REPLACE INTO reviews VALUES (?,?,?)',(doc['doc_id'],signature,json.dumps(review)))
                    cache.commit()
                checks.append(review['record'])
                for target,key in [(themes,'themes'),(sentiments,'sentiments'),(entities,'entities'),(associations,'associations'),(gaps,'gaps')]:target.extend(review.get(key,[]))
            except Exception as exc:
                errors.append(dict(doc_id=doc['doc_id'],error=repr(exc)))
                event('audit_record_failed',level='ERROR',doc_id=doc['doc_id'],error=repr(exc))
            if (i+1)%200==0:event('content_audit_progress',reviewed=i+1,total=len(docs),cached=reused,errors=len(errors))
    finally:cache.close()
    write_table(stage,'record_checks.csv',checks,['doc_id','source','flags'])
    theme_df=write_table(stage,'theme_evidence.csv',themes,['doc_id','source','year','theme','focus_status'])
    entity_df=write_table(stage,'entity_contexts.csv',entities,['doc_id','entity','entity_type','mentions'])
    association_df=write_table(stage,'association_checks.csv',associations,['doc_id','brand','theme'])
    write_table(stage,'candidate_missing_themes.csv',gaps,['doc_id','source','theme','lead_probe','disposition','url'])
    baseline=table('sentiment_unvalidated.csv')
    cmp=frame(sentiments,['doc_id','theme','vader_label','vader_mean','context_sentences','negation_or_contrast_sentences','focus_status'])
    cmp=baseline.merge(cmp,on=['doc_id','theme'],how='outer',validate='one_to_one',indicator=True)
    cmp['models_agree']=cmp.label==cmp.vader_label
    cmp['disposition']=cmp.apply(lambda r:'not_target_specific' if r.focus_status!='focus_supported' else 'model_disagreement' if not r.models_agree else 'lexical_agreement_only',axis=1)
    write_table(stage,'sentiment_comparison.csv',cmp,[])
    focus=theme_df[theme_df.focus_status=='focus_supported']
    group=[]
    for (source,year),subset in core.groupby(['source','year']):
        for theme in tags.theme.unique():
            n=int(((focus.source==source)&(focus.year.astype(str)==str(year))&(focus.theme==theme)).sum())
            group.append(dict(source=source,year=year,theme=theme,focus_articles=n,denominator=len(subset),focus_share_pct=100*n/len(subset),partial_year=int(year) in (2016,2026)))
    write_table(stage,'topic_focus_by_source_year.csv',group,['source','year','theme','focus_articles','denominator','focus_share_pct','partial_year'])
    summary=json.loads((output/'run_summary.json').read_text('utf-8')); start=summary['current_window_start']
    write_table(stage,'current_rank_sensitivity.csv',rank_scenarios(core,tags,start),['scenario','theme','share_pct','sources','denominator','rank'])
    write_table(stage,'current_focus_rank_sensitivity.csv',rank_scenarios(core,focus,start),['scenario','theme','share_pct','sources','denominator','rank'])
    # Review every NMF cluster with its source concentration and observed examples.
    clusters=table('discovered_topics_nmf.csv'); assignment=table('nmf_assignments.csv').merge(core[['doc_id','source','title']],on='doc_id')
    cluster_reviews=[]
    for r in clusters.to_dict('records'):
        assigned=assignment[assignment.cluster==r['cluster']]; counts=assigned.source.value_counts()
        dominant=counts.index[0] if len(counts) else ''; share=float(counts.iloc[0]/len(assigned)) if len(counts) else 0
        cluster_reviews.append(dict(cluster=r['cluster'],label=cluster_label(r['top_terms']),label_method='automated_term_interpretation',
            documents=len(assigned),dominant_source=dominant,dominant_source_share=share,
            source_concentrated=share>=.8,top_terms=r['top_terms'],example_urls=r['example_urls'],
            disposition='descriptive_cluster_only'))
    write_table(stage,'nmf_cluster_review.csv',cluster_reviews,['cluster','label','documents','dominant_source_share'])
    coverage=[]
    for source in SOURCES:
        for year in range(int(START[:4]),int(END[:4])+1):
            n=int(((core.source==source)&(core.year.astype(int)==year)).sum())
            coverage.append(dict(source=source,year=year,articles=n,observed=n>0,small_sample=n<20,
                partial_year=year in (int(START[:4]),int(END[:4])),interpretation='no_observations_not_zero_discussion' if not n else 'collected_sample_only'))
    write_table(stage,'coverage_audit.csv',coverage,['source','year','articles','observed','small_sample','partial_year','interpretation'])
    # Checks on audit coverage/joins, not re-use of its own confidence score as truth.
    integrity=[]
    def verify(name,good):
        integrity.append(dict(check=name,passed=bool(good)))
        if not good:errors.append(dict(check=name,error='Audit coverage/evidence inconsistency'))
    verify('all_saved_records_audited',len(checks)==len(docs) and {r['doc_id'] for r in checks}=={d['doc_id'] for d in docs})
    verify('all_theme_assignments_have_evidence',set(zip(theme_df.doc_id,theme_df.theme))==set(zip(tags.doc_id,tags.theme)) and len(theme_df)==len(tags))
    expected=table('entity_mentions.csv')
    verify('all_entity_mentions_reviewed',set(zip(entity_df.doc_id,entity_df.entity))==set(zip(expected.doc_id,expected.entity)) and len(entity_df)==len(expected))
    expected=table('brand_theme_evidence.csv')
    verify('all_brand_associations_reviewed',set(zip(association_df.doc_id,association_df.brand,association_df.theme))==set(zip(expected.doc_id,expected.brand,expected.theme)) and len(association_df)==len(expected))
    verify('all_sentiment_rows_compared',len(cmp)==len(baseline) and (cmp['_merge']=='both').all())
    verify('all_nmf_clusters_reviewed',len(cluster_reviews)==len(clusters))
    # Artifact hashes certify the analysis snapshot that the audit actually read.
    from .validate import validate
    structural=validate(root=root); atomic_json(output/'QUALITY_CHECKS.json',structural)
    verify('structural_audit',not structural['errors'])
    verify('analysis_snapshot_unchanged',json.loads((output/'analysis_state.json').read_text('utf-8'))==manifest)
    date_counts=Counter(r['date_check'] for r in checks);flags=Counter(f for r in checks for f in r['flags'].split(';') if f)
    result=dict(status='completed_with_limitations' if not errors else 'failed',created_at=now(),analysis_run_id=manifest.get('run_id'),
        analysis_fingerprint=manifest.get('input_fingerprint'),audit_version=version,lexicon_sha256=lexicon_hash,
        counts=dict(documents_reviewed=len(checks),core_articles=len(core),theme_assignments_reviewed=len(themes),
                    entity_rows_reviewed=len(entities),brand_associations_reviewed=len(associations),sentiment_rows_compared=len(cmp),
                    nmf_clusters_reviewed=len(clusters),possible_missing_theme_probes=len(gaps),
                    focus_supported_assignments=len(focus),incidental_or_uncertain_assignments=len(themes)-len(focus),cached_records=reused),
        date_evidence_counts=dict(date_counts),record_flag_counts=dict(flags),checks=integrity,errors=errors,
        sentiment=dict(models=['TextBlob','NLTK VADER'],agreement_pct=round(100*float(cmp.models_agree.mean()),2) if len(cmp) else None,
                       interpretation='model_agreement_is_not_accuracy; neither method establishes target-specific stance'),
        process_complete=not errors,ground_truth_accuracy_established=False,historical_completeness_established=False,
        policy=dict(focus='title match OR >=2 lead hits OR >=3 supporting sentences with >=2 distinct matched terms',
                    raw_support='up to 200 evenly spaced five-grams; warning below 0.85',vader_threshold=.05,textblob_threshold=.1,
                    small_source_threshold=20,source_concentration_threshold=.8),
        limitations=['Automated evidence/salience tests are heuristic and do not estimate precision or recall.',
                     'Matching saved raw text verifies provenance, not the truth of publisher statements.',
                     'PDF layout and unavailable historical pages are not certified.',
                     'Model agreement is not labelled sentiment accuracy.',
                     'Coverage gaps remain explicitly represented; automated completion is not a nine-source census.'])
    report=['# Automated research audit',f"\nStatus: **{result['status']}**. Analysis run: `{result['analysis_run_id']}`.",
        '\nThis audit runs to completion without human annotation. It audits every saved record and every published theme, entity, association and sentiment row. It reports evidence support, sensitivity and limitations; it does not invent ground-truth accuracy.',
        '\n## Completed checks\n',*[f'- {k}: {v:,}' for k,v in result['counts'].items()],
        '\n## Record/date evidence\n',*[f'- {k}: {v:,}' for k,v in date_counts.items()],
        '\n## Automatically applied interpretation\n',
        '- Use `theme_evidence.csv` and `topic_focus_by_source_year.csv` to distinguish literal mentions from stronger focus evidence. This focus rule is a sensitivity analysis, not a validated classifier.',
        '- Use `current_rank_sensitivity.csv` to compare source balancing, exclusion of sources with fewer than 20 current articles, and every leave-one-source-out scenario.',
        '- `candidate_missing_themes.csv` records alternative lead-text probes. They are retained as uncertainty, not silently counted as confirmed themes.',
        '- `entity_contexts.csv` records literal evidence and career-history contexts. `association_checks.csv` distinguishes same-sentence co-occurrence from weaker window-only matches; neither proves ownership or partnership.',
        f"- TextBlob/VADER agreement: {result['sentiment']['agreement_pct']}%. `sentiment_comparison.csv` records every agreement, disagreement, and contrast/negation context. Agreement is not accuracy; do not infer industry attitudes.",
        '- `nmf_cluster_review.csv` labels every cluster automatically and quantifies source concentration. These are descriptive lexical groups.',
        '- `coverage_audit.csv` retains every source/year cell, including absent observations and partial boundary years.',
        '\n## Limitations retained by the completed audit\n',*['- '+s for s in result['limitations']],
        '\nDetailed evidence excerpts are local QA material. The diagnostics ZIP contains only the summary and report, not these text-bearing CSVs.',
        '\nMethod: NLTK VADER documentation: https://www.nltk.org/api/nltk.sentiment.vader.html. The vendored lexicon hash and all thresholds are in summary.json.']
    atomic_json(stage/'summary.json',result);atomic_bytes(stage/'AUDIT_REPORT.md','\n'.join(report).encode('utf-8'))
    artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir() if p.is_file()}
    atomic_json(destination/'audit_state.json',dict(status='publishing',analysis_run_id=result['analysis_run_id']))
    for name in artifacts:atomic_bytes(destination/name,(stage/name).read_bytes())
    atomic_json(destination/'audit_state.json',dict(status='complete' if not errors else 'failed',analysis_run_id=result['analysis_run_id'],
        analysis_fingerprint=result['analysis_fingerprint'],audit_version=version,artifacts=artifacts))
    event('automated_audit_finished',status=result['status'],counts=result['counts'],errors=len(errors))
    return result


def main():
    with RunLock(ROOT/'data/pipeline.lock'),heartbeat():
        result=run_audit()
    print(json.dumps(result,indent=2))
    return 0 if result['process_complete'] else 1


if __name__=='__main__':raise SystemExit(main())
