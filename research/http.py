"""Polite, cached HTTP with durable failures and bounded retries."""
import gzip
import hashlib
import http.client
import json
import os
import random
import ssl
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, urlsplit, urlunsplit, quote
from .robots import PublisherRobots as RobotFileParser
from .config import DATA, SOURCES, USER_AGENT
from .store import now, set_source_state
from .runtime import atomic_bytes, atomic_json, check_stop, event, exception, pause, StopRequested

MAX_ATTEMPTS = 3
MAX_BYTES = 30_000_000
TRANSIENT_CODES = {408, 425, 429, 500, 502, 503, 504}
MIN_REQUEST_DELAY_SECONDS = 3.0

def later(seconds):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()

def retry_after(value):
    try:
        return max(0, float(value))
    except (ValueError, TypeError):
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            return max(0, (date-datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None

class FetchError(RuntimeError):
    def __init__(self, message, category, status=None, retryable=False, next_retry_at=None):
        super().__init__(message)
        self.category, self.status = category, status
        self.retryable, self.next_retry_at = retryable, next_retry_at

def same_host(url, base):
    return (urlparse(url).hostname or '').removeprefix('www.') == (urlparse(base).hostname or '').removeprefix('www.')

class CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, fetcher):
        self.fetcher = fetcher
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            self.fetcher.allowed(newurl, obey=self.fetcher.obey)
        except FetchError as exc:
            event('http_redirect_rejected',level='WARNING',source=self.fetcher.source,
                  url=req.full_url,target=newurl,status=code,reason=str(exc))
            raise
        event('http_redirect', level='DEBUG', source=self.fetcher.source, url=req.full_url, target=newurl, status=code)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

class Fetcher:
    def __init__(self, source, db, delay=MIN_REQUEST_DELAY_SECONDS):
        self.source, self.db, self.delay = source, db, delay
        self.last, self.robot, self.robot_status, self.stopped = 0, None, None, False
        self.obey = True
        self.opener = urllib.request.build_opener(CheckedRedirect(self))

    def allowed(self, url, obey=True):
        if urlsplit(url).scheme not in ('http','https') or not same_host(url, SOURCES[self.source]['base']):
            raise FetchError('Outside registered source host', 'external_redirect')
        if obey and self.robot is not None and not self.robot.can_fetch(USER_AGENT, url):
            raise FetchError('robots.txt disallows this URL', 'robots_disallowed')

    def available(self):
        state = self.db.execute('SELECT * FROM source_state WHERE source=?',(self.source,)).fetchone()
        if state and state['state']=='blocked':
            self.stopped = True
            raise FetchError(state['reason'], 'access_denied', status=403)
        if state and state['state']=='cooldown':
            if state['until_at'] and state['until_at'] > now():
                self.stopped = True
                raise FetchError(state['reason'], 'source_cooldown', retryable=True, next_retry_at=state['until_at'])
            set_source_state(self.db, self.source, 'ready')

    def record(self, url, purpose, attempt, started, status=None, error='', category='', size=0, cache=False):
        elapsed = round((time.monotonic()-started)*1000)
        self.db.execute('''INSERT INTO requests(source,url,checked_at,status,error,purpose,
            run_id,attempt,elapsed_ms,bytes,cache_hit,category) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
            (self.source,url,now(),status,error,purpose,os.environ.get('TOURISM_RUN_ID'),attempt,elapsed,size,int(cache),category))
        self.db.commit()
        event('http_attempt', level='DEBUG' if not error else 'WARNING', source=self.source,
              url=url,purpose=purpose,attempt=attempt,max_attempts=MAX_ATTEMPTS,status=status,
              elapsed_ms=elapsed,bytes=size,cache_hit=cache,error=error,error_kind=category)

    def remember_failure(self, url, error):
        self.db.execute('INSERT OR REPLACE INTO fetch_failures VALUES(?,?,?,?,?,?,?,?)',
            (self.source,url,error.category,error.status,str(error),int(error.retryable),error.next_retry_at,now()))
        self.db.commit()

    def request_delay(self):
        # Persisted request history also covers transitions between discovery,
        # backfill, crawling and separate invocations of the launcher.
        previous=self.db.execute('''SELECT checked_at FROM requests WHERE source=?
            AND COALESCE(cache_hit,0)=0 ORDER BY id DESC LIMIT 1''',(self.source,)).fetchone()
        persisted=0
        if previous:
            elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(previous['checked_at'])).total_seconds()
            persisted=max(0,self.delay-elapsed)
        return max(0,self.delay-(time.monotonic()-self.last),persisted)

    def fetch(self, url, purpose='article', obey=True, json_payload=None):
        check_stop(DATA, self.source)
        self.available()
        self.allowed(url, obey)
        self.obey = obey
        body = None
        if json_payload is not None:
            if self.source!='wttc' or urlsplit(url).path!='/component/search/index':
                raise ValueError('JSON POST is restricted to the observed public WTTC search component')
            body=json.dumps(json_payload,sort_keys=True,separators=(',',':')).encode('utf-8')
            # Separate read-only search requests by body, both in cache and failure ledger.
            # The fragment is local provenance and is never sent to the server.
            url=url.split('#')[0]+'#post='+hashlib.sha256(body).hexdigest()
        previous = self.db.execute('SELECT * FROM fetch_failures WHERE source=? AND url=?',(self.source,url)).fetchone()
        if previous and (not previous['retryable'] or (previous['next_retry_at'] or '')>now()):
            event('fetch_deferred', level='DEBUG', source=self.source,url=url,reason=previous['category'],next_retry_at=previous['next_retry_at'])
            raise FetchError(previous['error'],previous['category'],previous['status'],bool(previous['retryable']),previous['next_retry_at'])
        cache = DATA/'http_cache'/self.source
        key = hashlib.sha256(url.encode()).hexdigest()
        meta_path, data_path = cache/(key+'.json'), cache/(key+'.gz')
        if meta_path.exists() and data_path.exists():
            started = time.monotonic()
            try:
                meta = json.loads(meta_path.read_text('utf-8'))
                data = gzip.decompress(data_path.read_bytes())
                if meta.get('sha256') and meta['sha256'] != hashlib.sha256(data).hexdigest():
                    raise ValueError('Cache checksum mismatch')
                age = (datetime.now(timezone.utc)-datetime.fromisoformat(meta['retrieved_at'])).total_seconds()
                if purpose!='robots' or age<86400:
                    self.record(url,purpose,0,started,meta['status'],size=len(data),cache=True)
                    return data, meta
                event('cache_expired', level='DEBUG',source=self.source,url=url,purpose=purpose,age_seconds=int(age))
            except (OSError, ValueError, KeyError, EOFError, TypeError):
                exception('cache_corrupt_refetch', source=self.source,url=url)
        elif meta_path.exists() or data_path.exists():
            event('cache_incomplete_refetch',level='WARNING',source=self.source,url=url)
        parts = urlsplit(url)
        request_url = urlunsplit((parts.scheme,parts.netloc,
            quote(parts.path,safe='/:%@-_.~!$&()*+,;='),quote(parts.query,safe='=&%/:?@-_.~!$()*+,;'),''))
        headers={'User-Agent':USER_AGENT}
        if body is not None:headers['Content-Type']='application/json'
        req = urllib.request.Request(request_url,data=body,headers=headers)
        for attempt in range(1, MAX_ATTEMPTS+1):
            wait=self.request_delay()
            if wait>0:
                event('politeness_wait',level='DEBUG',source=self.source,url=url,wait_seconds=round(wait,3))
            pause(wait,DATA,self.source)
            check_stop(DATA, self.source)
            self.last = started = time.monotonic()
            status, size, wait = None, 0, None
            try:
                event('http_started',level='DEBUG',source=self.source,url=url,purpose=purpose,attempt=attempt)
                with self.opener.open(req,timeout=35) as response:
                    status = response.status
                    chunks = []
                    while True:
                        check_stop(DATA,self.source)
                        chunk = response.read(65536)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size>MAX_BYTES:
                            raise FetchError('Response exceeds 30 MB cap','size_limit')
                        chunks.append(chunk)
                    data = b''.join(chunks)
                    meta = dict(url=url,final_url=response.geturl(),status=status,
                        content_type=response.headers.get('Content-Type',''),retrieved_at=now(),
                        sha256=hashlib.sha256(data).hexdigest(),bytes=size)
                    if body is not None:meta['request_json']=json_payload
                atomic_bytes(data_path,gzip.compress(data))
                atomic_json(meta_path,meta)
                self.db.execute('DELETE FROM fetch_failures WHERE source=? AND url=?',(self.source,url))
                self.record(url,purpose,attempt,started,status,size=size)
                return data,meta
            except urllib.error.HTTPError as exc:
                status = exc.code
                wait = retry_after(exc.headers.get('Retry-After')) if exc.headers else None
                exc.close()
                category = 'access_denied' if status in (401,403) else ('rate_limited' if status==429 else 'http_error')
                error = FetchError(f'HTTP {status}: {exc.reason}',category,status,status in TRANSIENT_CODES)
                if status in (401,403):
                    set_source_state(self.db,self.source,'blocked',str(error))
                    self.stopped = True
                elif status==429 or (error.retryable and wait is not None):
                    error.next_retry_at = later(max(wait or 0,60 if status==429 else 1))
                    set_source_state(self.db,self.source,'cooldown',str(error),error.next_retry_at)
                    self.stopped = True
            except (urllib.error.URLError, ConnectionError, TimeoutError, http.client.HTTPException) as exc:
                certificate = isinstance(getattr(exc,'reason',exc),ssl.SSLCertVerificationError)
                error = FetchError(str(exc),'tls_configuration' if certificate else 'transport',retryable=not certificate)
            except FetchError as exc:
                error = exc
            except (KeyboardInterrupt, StopRequested):
                self.record(url,purpose,attempt,started,status,'Interrupted','interrupted',size)
                raise
            except Exception:
                exception('http_unexpected_error',source=self.source,url=url,attempt=attempt)
                raise
            self.record(url,purpose,attempt,started,status,str(error),error.category,size)
            if error.retryable and attempt<MAX_ATTEMPTS and not self.stopped:
                seconds = 2**attempt + random.uniform(0,.5)
                event('http_retry_scheduled',level='WARNING',source=self.source,url=url,attempt=attempt,next_attempt=attempt+1,wait_seconds=round(seconds,2))
                pause(seconds,DATA,self.source)
                continue
            if error.retryable and not error.next_retry_at:
                error.next_retry_at = later(300)
            self.remember_failure(url,error)
            raise error

    def robots(self):
        url = SOURCES[self.source]['base']+'/robots.txt'
        try:
            data,meta = self.fetch(url,purpose='robots',obey=False)
            text = data.decode('utf-8','replace')
            if '<html' in text[:500].lower():
                raise FetchError('HTML returned instead of robots.txt','robots_invalid')
            self.robot = RobotFileParser(url)
            self.robot.parse(text.splitlines())
            delay = self.robot.crawl_delay(USER_AGENT) or self.robot.crawl_delay('*')
            if delay:
                self.delay = max(self.delay,float(delay))
            self.robot_status = 'readable'
            return text
        except FetchError as exc:
            if exc.status==404:
                self.robot_status = 'not_found_404'
                self.robot = RobotFileParser(url)
                self.robot.parse(['User-agent: *','Allow: /'])
                return ''
            self.robot_status = 'unavailable'
            raise
