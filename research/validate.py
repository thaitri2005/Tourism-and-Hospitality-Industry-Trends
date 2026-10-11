"""Read-only checks of a finished local research snapshot; no publisher requests.

Run with .venv/Scripts/python.exe -m research.validate after the runner exits.
Exit 0 means structural checks passed, not that research findings are validated.
"""
import csv
import gzip
import hashlib
import json
import math
import re
import sqlite3
import zlib
from collections import Counter
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from .config import ROOT, START, END, SOURCES
from .discover import content_url
from .extract import DATE_RE, normalize_date
from .run import analysis_fingerprint
from .runtime import atomic_json
from .store import now


def artifact_errors(output, manifest):
    errors=[]
    if manifest.get('status')!='complete' or not manifest.get('artifacts'):
        errors.append('Missing completed artifact manifest')
    for name, expected in manifest.get('artifacts',{}).items():
        path=output/name
        if not path.is_file():errors.append('Missing artifact: '+name)
        elif hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            errors.append('Artifact hash mismatch: '+name)
    return errors


def validate():
    output=ROOT/'output'
    db=sqlite3.connect((ROOT/'data/corpus.sqlite').as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    db.execute('BEGIN')
    checks=[];errors=[];warnings=[]
    def check(name, failures=()):
        failures=list(failures)
        checks.append(dict(check=name,passed=not failures,failures=len(failures)))
        errors.extend(dict(check=name,detail=str(x)) for x in failures)
    def table(name):
        with (output/'tables'/name).open(encoding='utf-8-sig',newline='') as f:
            return list(csv.DictReader(f))
    def counts(rows, keys):return Counter(tuple(r[k] for k in keys) for r in rows)
    def close(a,b):return abs(float(a)-float(b))<0.011
    docs=[dict(r) for r in db.execute('SELECT * FROM documents')]
    urls=[dict(r) for r in db.execute('SELECT * FROM urls')]
    by_id={r['doc_id']:r for r in docs};by_url={r['url']:r for r in urls}
    check('sqlite_integrity',[r[0] for r in db.execute('PRAGMA integrity_check') if r[0]!='ok'])
    bad=[]
    for r in docs:
        if by_url.get(r['url'],{}).get('status')!='extracted':bad.append(r['doc_id'])
    doc_urls={r['url'] for r in docs}
    bad.extend(r['url'] for r in urls if r['status']=='extracted' and r['url'] not in doc_urls)
    check('document_queue_references',bad)
    bad=[];raw_bad=[];eligible_bad=[]
    for r in docs:
        norm=re.sub(r'\W+',' ',r['body'].lower()).strip()
        if (hashlib.sha256(norm.encode()).hexdigest()!=r['content_hash'] or
                len(re.findall(r'\b\w+\b',r['body']))!=r['word_count'] or
                hashlib.sha256(r['url'].encode()).hexdigest()[:20]!=r['doc_id']):
            bad.append(r['doc_id'])
        try:
            if not gzip.decompress((ROOT/r['raw_path']).read_bytes()):raw_bad.append(r['doc_id']+': empty')
        except (OSError,EOFError,zlib.error) as exc:raw_bad.append(r['doc_id']+': '+str(exc))
        if r['eligible'] and not (r['published_at'] and START<=r['published_at']<=END
                and r['language']=='en' and r['word_count']>=(60 if r['content_type']=='report_summary' else 120)
                and r['title'] and not r['exclusion_reason']):eligible_bad.append(r['doc_id'])
    check('document_hashes_ids_word_counts',bad)
    check('all_raw_files_readable',raw_bad)
    check('eligible_record_constraints',eligible_bad)
    manifest=json.loads((output/'analysis_state.json').read_text('utf-8'))
    check('published_artifact_hashes',artifact_errors(output,manifest))
    check('analysis_matches_database_and_code',[] if analysis_fingerprint(db)==manifest.get('input_fingerprint') else ['Stale analysis fingerprint'])
    core=table('core_article_metadata.csv');reports=table('report_metadata.csv');metadata=table('document_metadata.csv')
    ids={r['doc_id'] for r in core};eligible_ids={r['doc_id'] for r in docs if r['eligible']}
    check('metadata_export',[] if {r['doc_id'] for r in metadata}==set(by_id) and len(metadata)==len(docs) else ['Metadata count/IDs differ'])
    bad=[r['doc_id'] for r in core+reports if r['doc_id'] not in eligible_ids]
    for r in core+reports:
        if r['doc_id'] in by_id and any(str(by_id[r['doc_id']][k])!=r[k] for k in ['source','title','published_at','word_count','content_hash']):bad.append(r['doc_id'])
    check('analysis_record_metadata',bad)
    check('within_source_year_deduplication',[k for k,n in counts(core,['source','year','story_id']).items() if n>1])
    summary=json.loads((output/'run_summary.json').read_text('utf-8'))
    current=[r for r in core if r['published_at']>=summary['current_window_start']]
    expected=dict(extracted_documents=len(docs),eligible_documents=len(eligible_ids),core_articles=len(core),
        report_records=len(reports),unique_story_clusters=len({r['story_id'] for r in core}),current_articles=len(current),
        unprocessed_candidates=sum(r['status'] in ('discovered','retry_wait','in_progress') for r in urls))
    check('summary_counts',[k for k,v in expected.items() if summary.get(k)!=v])
    source_counts=counts(core,['source']);year_counts=counts(core,['source','year'])
    coverage=table('coverage_by_source_year.csv')
    check('source_year_coverage',[] if {(r['source'],r['year']):int(r['articles']) for r in coverage}==dict(year_counts) else ['Coverage counts differ'])
    tags=table('theme_assignments.csv');entities=table('entity_mentions.csv');sentiment=table('sentiment_unvalidated.csv')
    assoc=table('brand_theme_evidence.csv');assignments=table('nmf_assignments.csv')
    check('derived_document_references',[name+': '+r['doc_id'] for name,rows in [('themes',tags),('entities',entities),('sentiment',sentiment),('brands',assoc),('nmf',assignments)] for r in rows if r['doc_id'] not in ids])
    check('unique_theme_assignments',[k for k,n in counts(tags,['doc_id','theme']).items() if n!=1])
    tag_year=counts(tags,['source','year','theme']);tag_source=counts(tags,['source','theme'])
    bad=[]
    for filename,keys,denoms,nums in [('themes_by_source_year.csv',['source','year'],year_counts,tag_year),('themes_by_source.csv',['source'],source_counts,tag_source)]:
        for r in table(filename):
            key=tuple(r[k] for k in keys);n=nums[key+(r['theme'],)];d=denoms[key]
            if not d or int(r['articles'])!=n or int(r['denominator'])!=d or not close(r['share_pct'],100*n/d):bad.append((filename,key,r['theme']))
    check('annual_and_source_theme_arithmetic',bad)
    current_ids={r['doc_id'] for r in current};current_tags=[r for r in tags if r['doc_id'] in current_ids]
    current_denoms=counts(current,['source']);current_nums=counts(current_tags,['source','theme']);bad=[]
    for r in table('current_theme_ranking.csv'):
        n=sum(v for (s,t),v in current_nums.items() if t==r['theme'])
        shares=[100*current_nums[(s,r['theme'])]/d for (s,),d in current_denoms.items()]
        mean=sum(shares)/len(shares) if shares else 0
        if (int(r['articles'])!=n or int(r['denominator'])!=len(current) or
                not close(r['article_share_pct'],100*n/max(len(current),1)) or not close(r['equal_source_share_pct'],mean)):bad.append(r['theme'])
    check('current_ranking_arithmetic',bad)
    bad=[]
    for r in table('entity_ranking.csv'):
        rows=[x for x in entities if (x['entity'],x['entity_type'])==(r['entity'],r['entity_type'])]
        if (int(r['documents'])!=len({x['doc_id'] for x in rows}) or int(r['sources'])!=len({x['source'] for x in rows})
                or int(r['mentions'])!=sum(int(x['mentions']) for x in rows)):bad.append(r['entity'])
    check('entity_ranking_arithmetic',bad)
    bad=[]
    for r in table('brand_theme_associations.csv'):
        n=len({x['doc_id'] for x in assoc if (x['brand'],x['theme'])==(r['brand'],r['theme'])})
        b=len({x['doc_id'] for x in entities if x['entity']==r['brand']});t=len({x['doc_id'] for x in tags if x['theme']==r['theme']})
        if not b or not t or (int(r['documents']),int(r['brand_documents']),int(r['theme_documents']))!=(n,b,t) or not close(r['association_share_pct'],100*n/b) or not close(r['lift'],n*len(core)/(b*t)):bad.append((r['brand'],r['theme']))
    check('brand_association_arithmetic',bad)
    check('sentiment_alignment',[] if counts(sentiment,['doc_id','theme'])==counts(tags,['doc_id','theme']) else ['Theme/sentiment keys differ'])
    check('sentiment_range',[r['doc_id'] for r in sentiment if not -1<=float(r['mean_polarity'])<=1 or r['label'] not in ('mixed','positive','neutral','negative')])
    ss=table('sentiment_summary_unvalidated.csv')
    check('sentiment_summary',[] if {(r['theme'],r['label']):int(r['documents']) for r in ss}==dict(counts(sentiment,['theme','label'])) else ['Sentiment counts differ'])
    model=json.loads((output/'nmf_model_metadata.json').read_text('utf-8'));bad=[]
    if model.get('status')=='exploratory_unreviewed':
        if {r['doc_id'] for r in assignments}!=ids or len(assignments)!=len(core):bad.append('NMF coverage differs')
        bad.extend(r['doc_id'] for r in assignments if not math.isfinite(float(r['weight'])) or float(r['weight'])<0)
        dominant=counts(assignments,['cluster'])
        bad.extend(r['cluster'] for r in table('discovered_topics_nmf.csv') if int(r['documents_dominant'])!=dominant[(r['cluster'],)])
    check('nmf_assignments_and_counts',bad)
    # Independently reconcile every saved archive headline with the URL inventory.
    missing=[];index_links=[];archive_cards=0;unavailable_pages=[]
    cp=db.execute("SELECT payload FROM checkpoints WHERE name='english_archive:untourism'").fetchone()
    pages=json.loads(cp[0]).get('next_page',0) if cp else 0
    for page in range(pages):
        archive='https://www.untourism.int/news?page='+str(page)
        path=ROOT/'data/http_cache/untourism'/(hashlib.sha256(archive.encode()).hexdigest()+'.gz')
        try:data=gzip.decompress(path.read_bytes())
        except (OSError,EOFError,zlib.error):unavailable_pages.append(page);continue
        soup=BeautifulSoup(data,'lxml')
        for card in soup.select('article.node--teaser'):
            a=card.select_one('h2 a[href]') or card.select_one('a[href]')
            if not a:continue
            time=card.select_one('time[datetime]');date=normalize_date(time.get('datetime')) if time else ''
            match=DATE_RE.search(card.get_text(' ',strip=True))
            date=date or (normalize_date(match.group()) if match else '')
            if date and not START<=date<=END:continue
            archive_cards+=1;url=urljoin('https://www.untourism.int',a['href'])
            if url not in by_url:
                item=dict(url=url,date=date,title=a.get_text(' ',strip=True),archive=archive)
                (missing if content_url('untourism',url,from_news_archive=True) else index_links).append(item)
    if missing:warnings.append(f'{len(missing)} saved UN archive article links are missing from inventory. Run python run_research.py to apply the corrected archive discovery.')
    if index_links:warnings.append(f'{len(index_links)} archive cards point to excluded/non-article URLs; manual resolution needed.')
    if unavailable_pages:warnings.append(f'{len(unavailable_pages)} archive pages were unavailable locally; reconciliation is incomplete.')
    active=sorted({r['source'] for r in core})
    warnings.append(f'Only {len(active)} of {len(SOURCES)} listed sources have core articles. Structural checks do not validate extraction accuracy, topic coding, sentiment, or historical completeness.')
    result=dict(created_at=now(),status='passed_structural_checks' if not errors else 'failed_structural_checks',
        analysis_run_id=manifest.get('run_id'),input_fingerprint=manifest.get('input_fingerprint'),
        checks=checks,errors=errors,warnings=warnings,counts=expected,
        archive_reconciliation=dict(pages=pages,cards_in_window=archive_cards,missing_article_links=missing,
            excluded_card_links=index_links,unavailable_pages=unavailable_pages),research_validated=False)
    db.close()
    return result


def main():
    result=validate()
    path=ROOT/'output/QUALITY_CHECKS.json'
    atomic_json(path,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('archive_reconciliation',)},indent=2))
    print('Full structural audit: '+str(path))
    return 0 if not result['errors'] else 1


if __name__=='__main__':raise SystemExit(main())
