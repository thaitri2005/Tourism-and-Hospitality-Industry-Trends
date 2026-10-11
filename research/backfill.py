"""Checkpoint every English UN archive page back to the requested cutoff."""
import json
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .config import SOURCES, START, ROOT, DATA
from .store import connect, add_url, record_audit, checkpoint, completed
from .http import Fetcher
from .extract import DATE_RE, normalize_date
from .discover import content_url
from .runtime import event, fingerprint, check_stop

def main():
    db = connect()
    source = 'untourism'
    base = SOURCES[source]['base']
    key = 'english_archive:'+source
    version = fingerprint(ROOT/'research/backfill.py',ROOT/'research/discover.py',ROOT/'research/config.py')
    try:
        if completed(db,key,version):
            event('archive_checkpoint_reused',source=source)
            return dict(status='complete',cached=True)
        prior = db.execute('SELECT * FROM checkpoints WHERE name=?',(key,)).fetchone()
        state = json.loads(prior['payload']) if prior and prior['fingerprint']==version else {}
        start_page = state.get('next_page',0)
        f = Fetcher(source,db,delay=1.3)
        f.robots()
        previous_count = db.execute('SELECT COUNT(*) FROM urls WHERE source=?',(source,)).fetchone()[0]
        # The cap bounds each invocation, not the lifetime of the archive walk.
        for page in range(start_page,start_page+201):
            check_stop(DATA,source)
            url = base+'/news?page='+str(page)
            data,meta = f.fetch(url,'archive_backfill')
            soup = BeautifulSoup(data,'lxml')
            dates = []
            cards = soup.select('article.node--teaser')
            if not cards:
                raise ValueError(f'No archive teaser cards on page {page}; template/end requires review')
            signature = fingerprint(extra=data.decode('utf-8','replace'))
            if signature==state.get('last_signature'):
                raise ValueError(f'Archive repeated the previous page at page {page}; pagination requires review')
            for card in cards:
                a = card.select_one('h2 a[href]') or card.select_one('a[href]')
                if not a:
                    continue
                article_url = urljoin(base,a['href'])
                time = card.select_one('time[datetime]')
                d = normalize_date(time.get('datetime')) if time else ''
                if not d:
                    match = DATE_RE.search(card.get_text(' ',strip=True))
                    d = normalize_date(match.group()) if match else ''
                if d:
                    dates.append(d)
                if not d or d>=START:
                    if content_url(source,article_url,from_news_archive=True):
                        add_url(db,source,article_url,url,hint_date=d,hint_title=a.get_text(' ',strip=True))
                    else:
                        event('archive_candidate_excluded',level='WARNING',source=source,url=article_url,
                              archive_url=url,title=a.get_text(' ',strip=True),date=d,
                              reason='not_an_in_scope_article_link')
            db.commit()
            complete = bool(dates and len(dates)==len(cards) and max(dates)<START)
            state = dict(next_page=page+1,last_signature=signature,date_min=min(dates) if dates else None,
                         date_max=max(dates) if dates else None,boundary_reached=complete)
            checkpoint(db,key,version,'complete' if complete else 'progress',state)
            event('archive_page_saved',level='DEBUG',source=source,page=page,cards=len(cards),**state)
            if page%10==0 or complete:
                event('archive_progress',source=source,page=page,**state)
            if complete:
                break
        current = db.execute('SELECT COUNT(*) FROM urls WHERE source=?',(source,)).fetchone()[0]
        row = db.execute('SELECT payload FROM audit WHERE source=?',(source,)).fetchone()
        audit = json.loads(row[0]) if row else {}
        audit.update(english_archive_pages_processed=state['next_page'],
                     archive_backfill_new_urls=current-previous_count,discovered_urls=current,
                     english_archive_boundary_reached=state['boundary_reached'])
        record_audit(db,source,audit)
        result = dict(status='complete' if state['boundary_reached'] else 'page_limit',
                      pages_processed_this_run=state['next_page']-start_page,new_urls=current-previous_count)
        event('archive_finished',source=source,**result)
        return result
    finally:
        db.close()

if __name__=='__main__':
    main()
