"""Reapply changed extractors to local raw documents, with per-document commits."""
import gzip
import hashlib
from .store import connect
from .config import ROOT, DATA
from .extract import extract_html, extract_pdf
from .crawl import extraction_version
from .runtime import atomic_bytes, event, exception, check_stop, StopRequested

def main():
    db = connect()
    version = extraction_version()
    count = errors = 0
    try:
        rows = db.execute("SELECT * FROM documents WHERE COALESCE(extractor_version,'')<>?",(version,)).fetchall()
        event('reextract_started',pending=len(rows),extractor_version=version)
        for record in rows:
            check_stop(DATA)
            row = dict(record)
            try:
                path = ROOT/row['raw_path']
                if not path.is_file():
                    key = hashlib.sha256(row['url'].encode()).hexdigest()
                    cached = DATA/'http_cache'/row['source']/(key+'.gz')
                    if not cached.is_file():
                        raise FileNotFoundError('Raw file and HTTP cache are both missing')
                    atomic_bytes(path,cached.read_bytes())
                data = gzip.decompress(path.read_bytes())
                hint = db.execute('SELECT * FROM urls WHERE url=?',(row['url'],)).fetchone()
                hint = dict(hint) if hint else {}
                meta = {'retrieved_at':row['retrieved_at']}
                if data.startswith(b'%PDF'):
                    doc = extract_pdf(row['source'],row['url'],data,meta,hint)
                else:
                    doc,_ = extract_html(row['source'],row['url'],data,meta,hint)
                doc['raw_path'] = row['raw_path']
                doc['extractor_version'] = version
                fields = list(doc)
                db.execute('INSERT OR REPLACE INTO documents ('+','.join(fields)+') VALUES ('+','.join('?' for _ in fields)+')',[doc[k] for k in fields])
                db.commit()
                count += 1
                event('document_reextracted',level='DEBUG',source=row['source'],url=row['url'],
                      eligible=doc['eligible'],exclusion_reason=doc['exclusion_reason'],
                      language=doc['language'],published_at=doc['published_at'],word_count=doc['word_count'])
                if count%100==0:
                    event('reextract_progress',updated=count,pending=len(rows)-count-errors,errors=errors)
            except StopRequested:
                raise
            except Exception:
                db.rollback()
                errors += 1
                exception('reextract_failed',source=row['source'],url=row['url'])
        result = dict(updated=count,errors=errors)
        event('reextract_finished',**result)
        return result
    finally:
        db.close()

if __name__=='__main__':
    main()
