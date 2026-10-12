"""Resume public publisher archive walks; completion means linked archive exhausted."""
import json
import re
from urllib.parse import urljoin, urlsplit, parse_qs

from bs4 import BeautifulSoup
from .config import SOURCES, ROOT, DATA
from .discover import content_url
from .http import Fetcher, same_host
from .runtime import fingerprint, event, check_stop
from .store import connect, add_url, checkpoint

ARCHIVES = {
    'hospitalitynet': ['/news', '/opinion'],
    'wttc': ['/news', '/blog'],
    'pata': ['/blog', '/press-release', '/member-chapter-news-1'],
    'ahla': ['/news'],
}


def parse_page(source, url, data):
    soup = BeautifulSoup(data, 'lxml')
    scope = soup.select_one('main') or soup
    links = sorted({urljoin(url, a['href']).split('#')[0]
                    for a in scope.select('a[href]')
                    if content_url(source, urljoin(url, a['href']))
                    and not urlsplit(urljoin(url, a['href'])).query})
    if source == 'hospitalitynet':
        links = [u for u in links if re.search(r'/(?:news|opinion)/\d+', urlsplit(u).path)]
    if not links:
        raise ValueError('Archive has no recognizable article links; do not mark exhausted')
    next_link = scope.select_one('a[rel~=next]') or scope.select_one('a[aria-label="Next page"]')
    next_url = urljoin(url, next_link['href']) if next_link else None
    if source == 'wttc':
        params = soup.select_one('input[x-ref="searchParams"]')
        expected = int(parse_qs(urlsplit(url).query).get('page', ['1'])[0])
        active = soup.select_one('.circled-selection--active')
        rendered = json.loads(params['value']).get('page') if params else (
            int(active.get_text(strip=True)) if active and active.get_text(strip=True).isdigit() else None)
        if rendered != expected:
            raise ValueError('WTTC did not render the requested archive page')
        button = soup.select_one('.listing-pagination__button--next:not([disabled])')
        if button:
            match = re.fullmatch(r'changePage\((\d+)\)', button.get('x-on:click', ''))
            if not match:
                raise ValueError('Unrecognized WTTC pagination control')
            next_url = url.split('?')[0] + '?page=' + match[1]
    if next_url and (not same_host(next_url, url) or
                     urlsplit(next_url).path.split('/')[1] != urlsplit(url).path.split('/')[1]):
        raise ValueError('Archive next link leaves its source or collection')
    return links, next_url


def run_source(source, max_pages=250):
    if source not in ARCHIVES:
        return {'status': 'not_configured'}
    db = connect()
    key = 'history:' + source
    version = fingerprint(ROOT/'research/history.py', extra=source)
    try:
        prior = db.execute('SELECT * FROM checkpoints WHERE name=?', (key,)).fetchone()
        state = json.loads(prior['payload']) if prior and prior['fingerprint'] == version else {
            'pending': [SOURCES[source]['base'] + p for p in ARCHIVES[source]],
            'visited': [], 'signatures': [], 'pages': 0, 'new_urls': 0,
        }
        if not state['pending']:
            event('history_checkpoint_reused', source=source, pages=state['pages'])
            return dict(status='complete', **state)
        fetcher = Fetcher(source, db)
        fetcher.robots()
        for _ in range(max_pages):
            if not state['pending']:
                break
            check_stop(DATA, source)
            url = state['pending'][0]
            page=int(parse_qs(urlsplit(url).query).get('page',['1'])[0]) if source=='wttc' else 1
            if source=='wttc' and page>1:
                initial,_=fetcher.fetch(url.split('?')[0], 'historical_archive_parameters')
                node=BeautifulSoup(initial,'lxml').select_one('input[x-ref="searchParams"]')
                if not node:raise ValueError('Missing public WTTC search parameters')
                payload=json.loads(node['value']);payload['page']=page
                data,meta=fetcher.fetch(SOURCES[source]['base']+'/component/search/index',
                                       'historical_archive',json_payload=payload)
            else:
                data, meta = fetcher.fetch(url, 'historical_archive')
            links, next_url = parse_page(source, url, data)
            signature = fingerprint(extra='\n'.join(links))
            if signature in state['signatures']:
                raise ValueError('Archive repeats an earlier article set: ' + url)
            if next_url in state['visited'] or next_url == url:
                raise ValueError('Archive pagination cycle: ' + url)
            before = db.execute('SELECT count(*) FROM urls WHERE source=?', (source,)).fetchone()[0]
            for link in links:
                add_url(db, source, link, url)
            after = db.execute('SELECT count(*) FROM urls WHERE source=?', (source,)).fetchone()[0]
            state['pending'].pop(0)
            if next_url and next_url not in state['pending']:
                state['pending'].insert(0, next_url)
            state['visited'].append(url)
            state['signatures'].append(signature)
            state['pages'] += 1
            state['new_urls'] += after - before
            # Queue insertion and cursor advancement commit together; reruns are idempotent.
            checkpoint(db, key, version, 'progress' if state['pending'] else 'complete', state)
            event('history_page_saved', source=source, url=url, articles=len(links),
                  new_urls=after-before, next_url=next_url, pages=state['pages'],
                  remaining_collections=len(state['pending']))
        return dict(status='page_limit' if state['pending'] else 'complete', **state)
    finally:
        db.close()
