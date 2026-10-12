"""Idempotent, evidence-based corrections applied after extraction, before analysis.

Keep narrow corpus QA rules separate so a new disposition does not require
parsing thousands of unchanged raw files. Raw downloads are never modified.
"""
import hashlib
import gzip
import json
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from .config import DATA
from .runtime import check_stop, event
from .store import connect


def curate_record(record, raw=None):
    doc=dict(record)
    flags=json.loads(doc.get('quality_flags') or '[]')
    reasons=[r for r in (doc.get('exclusion_reason') or '').split(';') if r]
    path=urlparse(doc['url']).path.rstrip('/')
    if doc['source']=='hospitalitynet' and raw:
        soup=BeautifulSoup(raw,'lxml')
        main=soup.select_one('article section[aria-label="Main content"]')
        if main:
            for node in main.select('script,style,aside,nav,footer'):
                node.decompose()
            body=main.get_text('\n',strip=True)
            if body!=doc['body']:
                doc['body']=body
                doc['word_count']=len(re.findall(r'\b\w+\b',body))
                doc['content_hash']=hashlib.sha256(re.sub(r'\W+',' ',body.lower()).strip().encode()).hexdigest()
                doc['duplicate_cluster']=doc['content_hash']
            marker='curation:v2_hospitalitynet_main_content_only'
            if marker not in flags:flags.append(marker)
            if doc['word_count']<120 and 'insufficient_text' not in reasons:reasons.append('insufficient_text')
    if doc['source']=='ahla' and path in ('/news/international','/news/hospitality-related-associations'):
        # The saved pages are a membership advertisement and an association
        # directory. Their WebPage dates do not turn them into news articles.
        if 'non_article_page' not in reasons:reasons.append('non_article_page')
        marker='curation:v1_ahla_membership_or_directory'
        if marker not in flags:flags.append(marker)
    if doc['source']=='pata':
        body=re.split(r'\nBack to Blog Homepage\s*>\s*\n',doc['body'],maxsplit=1)[0].strip()
        if body!=doc['body']:
            doc['body']=body
            doc['word_count']=len(re.findall(r'\b\w+\b',body))
            doc['content_hash']=hashlib.sha256(re.sub(r'\W+',' ',body.lower()).strip().encode()).hexdigest()
            doc['duplicate_cluster']=doc['content_hash']
            marker='curation:v1_pata_embedded_navigation_removed'
            if marker not in flags:flags.append(marker)
            minimum=60 if doc['content_type']=='report_summary' else 120
            if doc['word_count']<minimum and 'insufficient_text' not in reasons:reasons.append('insufficient_text')
    doc['quality_flags']=json.dumps(flags)
    doc['exclusion_reason']=';'.join(reasons)
    doc['eligible']=int(not reasons)
    return doc


def main():
    db=connect();changed=0
    try:
        rows=db.execute("SELECT * FROM documents WHERE source IN ('ahla','pata','hospitalitynet') ORDER BY doc_id").fetchall()
        for row in rows:
            check_stop(DATA)
            before=dict(row)
            raw=None
            if before['source']=='hospitalitynet':
                with gzip.open(before['raw_path'],'rb') as stream:raw=stream.read()
            after=curate_record(before,raw)
            fields=[k for k,v in after.items() if v!=before[k]]
            if not fields:continue
            db.execute('UPDATE documents SET '+','.join(k+'=?' for k in fields)+' WHERE doc_id=?',
                       [after[k] for k in fields]+[after['doc_id']])
            db.commit();changed+=1
            event('document_curated',doc_id=after['doc_id'],source=after['source'],url=after['url'],
                  changed_fields=fields,quality_flags=json.loads(after['quality_flags']),
                  exclusion_reason=after['exclusion_reason'],old_words=before['word_count'],new_words=after['word_count'])
        result=dict(reviewed=len(rows),updated=changed,errors=0)
        event('curation_finished',**result)
        return result
    finally:db.close()
