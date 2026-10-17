"""Fill historical and access gaps that the live publisher sites cannot.

Two routes, both resumable with per-document commits:

* Wayback Machine. The CDX index lists archived article URLs for a source; a
  deterministic per-year sample is fetched as the archived original (``id_``
  mode, no toolbar). Used where live automated access is refused (CTO and
  Travel Weekly answer every request with a Cloudflare/Sucuri 403) and where
  pre-2020 URLs no longer exist on the live site (WTTC, AHLA, PATA).
* Hospitality Net. Article IDs are sequential, so a uniform random ID sample
  across October 2016 - July 2026 is queued for the normal live crawler.

Archived documents keep the publisher URL as their URL. The snapshot is kept in
``urls.archive_snapshot`` and flagged on the document, so re-extraction from the
saved raw file reproduces the same record.
"""
import argparse
import gzip
import hashlib
import http.client
import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

from .config import DATA, ROOT, SOURCES, USER_AGENT
from .crawl import extraction_version
from .extract import extract_html
from .http import later
from .runtime import StopRequested, atomic_bytes, atomic_json, check_stop, event, exception, fingerprint, pause
from .store import add_url, checkpoint, completed, connect, now

CDX = 'https://web.archive.org/cdx/search/cdx'
WAYBACK = 'https://web.archive.org/web/{ts}id_/{original}'
WAYBACK_DELAY_SECONDS = 2.0
ARCHIVE_STATES = ('archive_queued', 'archive_retry')

SKIP_CTO = (r'^/(?:directory|category|events-calendar|media|our-work|destinations|resources|statistics|kb|gallery|'
            r'faq|tag|slider|about|contact|members?|login|cart|search|wp-|page|feed|privacy|terms|careers|sitemap|'
            r'buy-|membership|shop|store|20\d\d)')
SKIP_PATA = (r'^/(?:about|events?|store|membership|members?|contact|privacy|terms|category|tag|page|feed|wp-|'
             r'search|careers|sitemap|pata-?chapters?|chapters?|board|staff|ptm|login|cart)')

# quota: maximum URLs per first-capture year (None = all). capture_dates: undated
# pages may take their first archive capture as an upper-bound publication date.
PLANS = {
    'cto': [dict(query='onecaribbean.org/*', path=r'^/[a-z0-9][a-z0-9-]{8,}/$', skip=SKIP_CTO)],
    'travelweekly': [dict(query='travelweekly.com/Travel-News/*', frm='20160920', to='20261010',
                          path=r'^/Travel-News/[A-Za-z-]+/[^/]+$', quota=170, year_quota={2016: 60, 2026: 140})],
    # WTTC moved its press room in 2019; both generations of URLs carry the year.
    'wttc': [dict(query='wttc.org/media-centre/press-releases/press-releases/*',
                  path=r'^/media-centre/press-releases/press-releases/(?:2016|2017|2018|2019)/[^/]+/?$',
                  capture_dates=True),
             dict(query='wttc.org/about/media-centre/press-releases/press-releases/*',
                  path=r'^/about/media-centre/press-releases/press-releases/(?:2016|2017|2018|2019)/[^/]+/?$',
                  capture_dates=True)],
    'ahla': [dict(query='ahla.com/press-release/*', path=r'^/press-release/[^/]+$'),
             dict(query='ahla.com/index.php/press-release/*', path=r'^/press-release/[^/]+$', strip_prefix='/index.php')],
    'pata': [dict(query='pata.org/*', frm='20160920', to='20191231', path=r'^/[a-z0-9][a-z0-9-]{8,}/$',
                  skip=SKIP_PATA, quota=250, year_quota={2016: 80})],
}
HOSPITALITYNET_SAMPLE = dict(low=4078500, high=4133600, size=1800, seed=20161010)


class ArchiveMissing(RuntimeError):
    pass


class ArchiveRetry(RuntimeError):
    pass


class ArchiveOnly(urllib.request.HTTPRedirectHandler):
    """Follow Wayback's own timestamp redirects, never a redirect to the live site."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).hostname != 'web.archive.org':
            raise ArchiveMissing('Archived capture redirects to the live site: ' + newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Wayback:
    """Sequential, cached, rate-limited client for web.archive.org."""
    def __init__(self, db, source):
        self.db, self.source, self.last = db, source, 0.0
        self.opener = urllib.request.build_opener(ArchiveOnly())

    def record(self, url, purpose, attempt, started, status, size=0, error='', cache=False):
        self.db.execute('''INSERT INTO requests(source,url,checked_at,status,error,purpose,attempt,elapsed_ms,bytes,cache_hit,category)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''', (self.source, url, now(), status, error, purpose, attempt,
            round((time.monotonic()-started)*1000), size, int(cache), 'wayback'))
        self.db.commit()

    def get(self, url, purpose='archive_snapshot', attempts=4):
        cache = DATA/'http_cache'/'wayback'
        key = hashlib.sha256(url.encode()).hexdigest()
        data_path, meta_path = cache/(key+'.gz'), cache/(key+'.json')
        if data_path.is_file() and meta_path.is_file():
            started = time.monotonic()
            data = gzip.decompress(data_path.read_bytes())
            meta = json.loads(meta_path.read_text('utf-8'))
            self.record(url, purpose, 0, started, meta['status'], len(data), cache=True)
            return data, meta
        for attempt in range(1, attempts+1):
            pause(max(0.0, WAYBACK_DELAY_SECONDS-(time.monotonic()-self.last)), DATA, self.source)
            self.last = started = time.monotonic()
            request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            try:
                with self.opener.open(request, timeout=90) as response:
                    data = response.read()
                    meta = dict(url=url, final_url=response.geturl(), status=response.status,
                                content_type=response.headers.get('Content-Type', ''), retrieved_at=now(),
                                sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
                atomic_bytes(data_path, gzip.compress(data))
                atomic_json(meta_path, meta)
                self.record(url, purpose, attempt, started, meta['status'], len(data))
                return data, meta
            except urllib.error.HTTPError as exc:
                exc.close()
                self.record(url, purpose, attempt, started, exc.code, error=f'HTTP {exc.code}')
                if exc.code not in (429, 500, 502, 503, 504):
                    raise ArchiveMissing(f'HTTP {exc.code}')
                header = exc.headers.get('Retry-After') if exc.headers else None
                wait = float(header) if header and header.isdigit() else 30*attempt*attempt
                event('wayback_backoff', level='WARNING', source=self.source, url=url, status=exc.code, wait_seconds=wait)
                pause(wait, DATA, self.source)
            except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as exc:
                self.record(url, purpose, attempt, started, None, error=str(exc)[:300])
                pause(15*attempt, DATA, self.source)
        raise ArchiveRetry('Wayback did not answer after %d attempts' % attempts)


def cdx_rows(client, plan):
    params = [('url', plan['query']), ('fl', 'original,timestamp'), ('filter', 'statuscode:200'),
              ('filter', 'mimetype:text/html'), ('collapse', 'urlkey'), ('limit', '200000')]
    if plan.get('frm'):
        params.append(('from', plan['frm']))
    if plan.get('to'):
        params.append(('to', plan['to']))
    data, _ = client.get(CDX+'?'+urllib.parse.urlencode(params), purpose='archive_index', attempts=6)
    return [line.split(' ') for line in data.decode('utf-8', 'replace').splitlines() if line.count(' ') == 1]


def publisher_url(source, original, plan):
    path = urllib.parse.urlsplit(original).path
    if plan.get('strip_prefix') and path.startswith(plan['strip_prefix']):
        path = path[len(plan['strip_prefix']):]
    return urllib.parse.urlunsplit(('https', urllib.parse.urlsplit(SOURCES[source]['base']).netloc, path, '', ''))


def select(source, plan, rows):
    """Earliest capture per publisher URL, then a deterministic sample per capture year."""
    earliest = {}
    for original, ts in rows:
        parts = urllib.parse.urlsplit(original)
        if parts.query or not re.match(plan['path'], publisher_path(parts.path, plan)):
            continue
        if plan.get('skip') and re.match(plan['skip'], parts.path):
            continue
        url = publisher_url(source, original, plan)
        key = url.lower().rstrip('/')
        if key not in earliest or ts < earliest[key][1]:
            earliest[key] = (url, ts, original)
    by_year = defaultdict(list)
    for url, ts, original in earliest.values():
        by_year[int(ts[:4])].append((url, ts, original))
    chosen = []
    for year, items in sorted(by_year.items()):
        items.sort(key=lambda item: hashlib.sha256(item[0].encode()).hexdigest())
        quota = plan.get('year_quota', {}).get(year, plan.get('quota'))
        chosen.extend(items[:quota] if quota else items)
    return chosen, {year: len(items) for year, items in by_year.items()}


def capture_hint(url, ts):
    """Fallback date for an undated page: its first capture, unless the URL names an earlier year."""
    year = re.search(r'/(20\d\d)/', url)
    if year and year[1] != ts[:4]:
        return f'{year[1]}-07-01', 'wayback_cdx:url_year_only'
    return f'{ts[:4]}-{ts[4:6]}-{ts[6:8]}', 'wayback_cdx:first_capture'


def publisher_path(path, plan):
    if plan.get('strip_prefix') and path.startswith(plan['strip_prefix']):
        return path[len(plan['strip_prefix']):]
    return path


def discover(source):
    """Queue archive captures for a source once per plan version."""
    db = connect()
    key = 'archive_discovery:' + source
    version = fingerprint(ROOT/'research/archive.py', extra=source)
    try:
        if completed(db, key, version):
            event('archive_discovery_reused', source=source)
            return dict(status='checkpoint_reused')
        if source == 'hospitalitynet':
            return queue_hospitalitynet(db, key, version)
        client = Wayback(db, source)
        summary = dict(candidates_by_capture_year={}, queued=0, already_known=0)
        for plan in PLANS[source]:
            rows = cdx_rows(client, plan)
            chosen, available = select(source, plan, rows)
            summary['candidates_by_capture_year'][plan['query']] = available
            for url, ts, original in chosen:
                if db.execute('SELECT 1 FROM urls WHERE url=?', (url,)).fetchone():
                    summary['already_known'] += 1
                    continue
                hint, via = capture_hint(url, ts) if plan.get('capture_dates') else ('', 'wayback_cdx')
                add_url(db, source, url, via, hint_date=hint)
                db.execute("UPDATE urls SET status='archive_queued',archive_snapshot=? WHERE url=?", (ts+' '+original, url))
                summary['queued'] += 1
            db.commit()
        checkpoint(db, key, version, 'complete', summary)
        event('archive_discovery_finished', source=source, **summary)
        return dict(status='complete', **summary)
    finally:
        db.close()


def queue_hospitalitynet(db, key, version):
    spec = HOSPITALITYNET_SAMPLE
    ids = random.Random(spec['seed']).sample(range(spec['low'], spec['high']), spec['size'])
    before = db.execute("SELECT COUNT(*) FROM urls WHERE source='hospitalitynet'").fetchone()[0]
    for article_id in sorted(ids):
        add_url(db, 'hospitalitynet', f'https://www.hospitalitynet.org/news/{article_id}', 'id_sample:uniform')
    db.commit()
    queued = db.execute("SELECT COUNT(*) FROM urls WHERE source='hospitalitynet'").fetchone()[0]-before
    summary = dict(sample=spec, queued=queued)
    checkpoint(db, key, version, 'complete', summary)
    event('archive_discovery_finished', source='hospitalitynet', **summary)
    return dict(status='complete', **summary)


def fetch(source, limit=None):
    """Retrieve queued archive captures; each document commits separately."""
    db = connect()
    version = extraction_version()
    client = Wayback(db, source)
    saved = eligible = failed = 0
    try:
        rows = db.execute("""SELECT * FROM urls WHERE source=? AND (status='archive_queued'
            OR (status='archive_retry' AND COALESCE(next_retry_at,'')<=?))""", (source, now())).fetchall()
        rows = sorted(rows, key=lambda r: hashlib.sha256(r['url'].encode()).hexdigest())[:limit]
        event('archive_fetch_started', source=source, queued=len(rows))
        for row in rows:
            check_stop(DATA, source)
            url = row['url']
            ts, original = row['archive_snapshot'].split(' ', 1)
            try:
                data, meta = client.get(WAYBACK.format(ts=ts, original=original))
                meta = dict(meta, url=url)
                doc, _ = extract_html(source, url, data, meta, dict(row))
                raw = DATA/'raw'/source/(doc['doc_id']+'.html.gz')
                atomic_bytes(raw, gzip.compress(data))
                doc['raw_path'] = str(raw.relative_to(DATA.parent))
                doc['extractor_version'] = version
                fields = list(doc)
                db.execute('INSERT OR REPLACE INTO documents ('+','.join(fields)+') VALUES ('+','.join('?'*len(fields))+')',
                           [doc[k] for k in fields])
                db.execute("UPDATE urls SET status='extracted',error='',error_kind=NULL,next_retry_at=NULL,fetched_at=? WHERE url=?",
                           (now(), url))
                db.commit()
                saved += 1
                eligible += doc['eligible']
            except (KeyboardInterrupt, StopRequested):
                db.rollback()
                raise
            except ArchiveMissing as exc:
                db.rollback()
                failed += 1
                db.execute("UPDATE urls SET status='permanent_error',error=?,error_kind='archive_missing',fetched_at=? WHERE url=?",
                           (str(exc), now(), url))
                db.commit()
            except ArchiveRetry as exc:
                db.rollback()
                failed += 1
                db.execute("UPDATE urls SET status='archive_retry',error=?,error_kind='archive_unavailable',next_retry_at=? WHERE url=?",
                           (str(exc), later(1800), url))
                db.commit()
            except Exception as exc:
                db.rollback()
                failed += 1
                exception('archive_extraction_failed', source=source, url=url)
                db.execute("UPDATE urls SET status='archive_error',error=?,error_kind='extraction',fetched_at=? WHERE url=?",
                           (str(exc)[:500], now(), url))
                db.commit()
            if (saved+failed) % 25 == 0:
                event('archive_fetch_progress', source=source, saved=saved, eligible=eligible, failed=failed,
                      remaining=len(rows)-saved-failed)
        result = dict(status='queue_processed', saved=saved, eligible=eligible, failed=failed)
        event('archive_fetch_finished', source=source, **result)
        return result
    finally:
        db.close()


def run_source(source):
    """Discovery plus archived retrieval; Hospitality Net retrieval is the live crawl."""
    if source not in PLANS and source != 'hospitalitynet':
        return dict(status='not_configured')
    result = dict(discovery=discover(source))
    if source in PLANS:
        result['fetch'] = fetch(source)
    return result


def main():
    parser = argparse.ArgumentParser(description='Archive discovery/retrieval without the full runner.')
    parser.add_argument('--sources', nargs='+', default=list(PLANS)+['hospitalitynet'])
    parser.add_argument('--limit', type=int)
    parser.add_argument('--discover-only', action='store_true')
    args = parser.parse_args()
    for source in args.sources:
        print(json.dumps({source: discover(source)}, default=str), flush=True)
        if source in PLANS and not args.discover_only:
            print(json.dumps({source: fetch(source, args.limit)}, default=str), flush=True)


if __name__ == '__main__':
    main()
