"""Per-document commits and resumable collection; no successful URL is re-fetched."""
import argparse
import gzip
import hashlib
import importlib.metadata
import json
import os
import uuid
from .config import SOURCES, DATA, ROOT
from .store import connect, add_url, now, set_source_state
from .http import Fetcher, FetchError, same_host, later
from .extract import extract_html, extract_pdf
from .runtime import atomic_bytes, check_stop, event, exception, fingerprint, StopRequested

def extraction_version():
    versions={name:importlib.metadata.version(name) for name in ['beautifulsoup4','lxml','pypdf','python-dateutil']}
    return fingerprint(ROOT/'research/extract.py', ROOT/'research/config.py',extra=json.dumps(versions,sort_keys=True))

def recover(db):
    interrupted = db.execute("UPDATE urls SET status='discovered',error='Recovered interrupted item',next_retry_at=NULL WHERE status='in_progress'").rowcount
    db.execute("""UPDATE urls SET status='extracted',error='',error_kind=NULL
        WHERE status IN ('discovered','retry_wait') AND url IN (SELECT url FROM documents)""")
    legacy = db.execute("""UPDATE urls SET
        status=CASE WHEN error LIKE '%404%' OR error LIKE '%410%' THEN 'permanent_error' ELSE 'retry_wait' END,
        error_kind='legacy_error',next_retry_at=NULL WHERE status='fetch_or_extract_error'""").rowcount
    updated = db.execute("""UPDATE urls SET status='discovered',next_retry_at=NULL
        WHERE status='extraction_error' AND COALESCE(extractor_version,'')<>?""",(extraction_version(),)).rowcount
    db.commit()
    event('recovery',interrupted_items=interrupted,legacy_failures_migrated=legacy,extractor_fix_retries=updated)
    return interrupted

def run_source(source, limit=100000):
    db = connect()
    c = SOURCES[source]
    run_id = os.environ.get('TOURISM_RUN_ID') or uuid.uuid4().hex
    version = extraction_version()
    count = errors = eligible = consecutive_errors = 0
    status = 'queue_processed'
    try:
        if c['access']!='public_research_review':
            return dict(source=source,status=c['access'])
        if source=='untourism':
            for lang in ['es','fr','ru','ar','zh-hans','zh','de','pt']:
                db.execute("""UPDATE urls SET status='excluded_language_route'
                    WHERE source=? AND status IN ('discovered','retry_wait') AND url LIKE ?""",
                    (source,c['base']+'/'+lang+'/%'))
            db.commit()
        f = Fetcher(source,db)
        try:
            f.robots()
        except FetchError as exc:
            event('source_unavailable',level='WARNING',source=source,reason=str(exc),error_kind=exc.category,next_retry_at=exc.next_retry_at)
            return dict(source=source,status='source_unavailable',error=str(exc),error_kind=exc.category,next_retry_at=exc.next_retry_at)
        while count<limit:
            check_stop(DATA,source)
            rows = db.execute("""SELECT * FROM urls WHERE source=?
                AND (status='discovered' OR (status='retry_wait' AND COALESCE(next_retry_at,'')<=?))
                AND COALESCE(last_run,'')<>?""",(source,now(),run_id)).fetchall()
            if not rows:
                break
            # A partial run should not favor alphabetically early titles.
            rows.sort(key=lambda row:hashlib.sha256(row['url'].encode()).hexdigest())
            for item in rows:
                check_stop(DATA,source)
                if count>=limit or f.stopped:
                    break
                row = dict(item)
                url = row['url']
                db.execute("""UPDATE urls SET status='in_progress',attempts=attempts+1,
                    last_run=?,extractor_version=? WHERE url=?""",(run_id,version,url))
                db.commit()
                count += 1
                event('document_started',level='DEBUG',source=source,url=url,url_attempt=row['attempts']+1)
                try:
                    data,meta = f.fetch(url)
                    is_pdf = data.startswith(b'%PDF') or 'application/pdf' in meta['content_type']
                    if is_pdf:
                        doc = extract_pdf(source,url,data,meta,row)
                        links = []
                    else:
                        doc,links = extract_html(source,url,data,meta,row)
                    raw = DATA/'raw'/source/(doc['doc_id']+('.pdf.gz' if is_pdf else '.html.gz'))
                    atomic_bytes(raw,gzip.compress(data))
                    doc['raw_path'] = str(raw.relative_to(DATA.parent))
                    doc['extractor_version'] = version
                    fields = list(doc)
                    db.execute('INSERT OR REPLACE INTO documents ('+','.join(fields)+') VALUES ('+','.join('?' for _ in fields)+')',[doc[k] for k in fields])
                    db.execute("""UPDATE urls SET status='extracted',error='',error_kind=NULL,
                        next_retry_at=NULL,fetched_at=? WHERE url=?""",(now(),url))
                    for link in links:
                        if same_host(link['url'],c['base']):
                            add_url(db,source,link['url'],url,hint_date=doc['published_at'],hint_title=doc['title'])
                            if link['gated']:
                                db.execute("""UPDATE urls SET status='form_gated_report',
                                    error='Download form not submitted; no personal data provided'
                                    WHERE url=? AND status IN ('discovered','retry_wait')""",(link['url'],))
                    db.commit()
                    eligible += doc['eligible']
                    consecutive_errors = 0
                    event('document_saved',level='DEBUG',source=source,url=url,doc_id=doc['doc_id'],
                          published_at=doc['published_at'],date_evidence=doc['date_evidence'],
                          language=doc['language'],word_count=doc['word_count'],content_type=doc['content_type'],
                          eligible=bool(doc['eligible']),exclusion_reason=doc['exclusion_reason'],
                          quality_flags=doc['quality_flags'],raw_path=doc['raw_path'],extractor_version=version)
                except (KeyboardInterrupt,StopRequested):
                    db.rollback()
                    db.execute("UPDATE urls SET status='discovered',last_run=NULL WHERE url=? AND status='in_progress'",(url,))
                    db.commit()
                    event('document_interrupted',level='WARNING',source=source,url=url)
                    raise
                except Exception as exc:
                    db.rollback()
                    errors += 1
                    consecutive_errors += 1
                    if isinstance(exc,FetchError):
                        kind = exc.category
                        item_status = 'retry_wait' if exc.retryable else 'permanent_error'
                        retry_at = exc.next_retry_at
                    elif isinstance(exc,(OSError,)):
                        # Local disk/permission failures require attention; do not
                        # mislabel these as an article extraction problem.
                        exception('local_storage_failure',source=source,url=url)
                        db.execute("UPDATE urls SET status='discovered',last_run=NULL WHERE url=?",(url,))
                        db.commit()
                        raise
                    else:
                        kind,item_status,retry_at = 'extraction','extraction_error',None
                        exception('extraction_failed',source=source,url=url)
                    db.execute("""UPDATE urls SET status=?,error=?,error_kind=?,next_retry_at=?,
                        fetched_at=? WHERE url=?""",(item_status,str(exc),kind,retry_at,now(),url))
                    db.commit()
                    event('document_failed',level='WARNING',source=source,url=url,status=item_status,
                          error=str(exc),error_kind=kind,next_retry_at=retry_at)
                    if consecutive_errors>=5 and not f.stopped:
                        set_source_state(db,source,'cooldown','Five consecutive document failures',later(300))
                        f.stopped = True
                if count%25==0:
                    event('crawl_progress',source=source,attempted=count,new_eligible=eligible,errors=errors)
            if f.stopped:
                status = 'source_stopped'
                break
        remaining = db.execute("SELECT COUNT(*) FROM urls WHERE source=? AND status IN ('discovered','retry_wait','in_progress')",(source,)).fetchone()[0]
        result = dict(source=source,status=status,attempted=count,new_eligible=eligible,errors=errors,remaining=remaining)
        event('source_finished',**result)
        return result
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sources',nargs='+',default=['etc','wttc','untourism','cto'])
    parser.add_argument('--limit-per-source',type=int,default=100000)
    args = parser.parse_args()
    db = connect()
    recover(db)
    db.close()
    for source in args.sources:
        run_source(source,args.limit_per_source)

if __name__=='__main__':
    main()
