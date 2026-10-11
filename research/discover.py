import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import json
import re
from urllib.parse import urljoin, urlparse, urldefrag
from bs4 import BeautifulSoup
from lxml import etree
from .config import SOURCES, OUTPUT, ROOT, DATA
from .store import connect, record_audit, add_url, now, checkpoint
from .http import Fetcher, FetchError, same_host
from .runtime import event, exception, fingerprint, check_stop, StopRequested

def content_url(source,url,from_news_archive=False):
    c=SOURCES[source]
    if not url.startswith('http') or not same_host(url,c['base']):
        return False
    p=urlparse(url).path
    if source=='untourism' and re.match(r'^/(es|fr|ru|ar|zh-hans|zh|de|pt)(/|$)',p):
        return False
    if re.search(r'\.(jpg|png|gif|webp|svg|css|js|zip|mp4|xlsx?)$',p,re.I):
        return False
    if re.search(r'/(tag|category|author|page|feed|wp-json|wp-admin|events-calendar|product|cart|checkout|galleries|staff|members)/',p):
        return False
    if p.lower().endswith('.pdf'):
        return True
    # A dated headline card in the publisher's English news archive is stronger
    # article evidence than a modern URL prefix. Older UN routes include flat
    # slugs, /global/, /node/<id>, and even /new/. Never broaden sitemap crawling
    # to every path, or accept a card that points only to an archive index.
    if from_news_archive and source=='untourism':
        if p.rstrip('/') in ('','/news'):return False
        if p.startswith('/archive/'):
            # /archive/global/ is an index, but /archive/<region>/news/... and
            # /press-release/... are genuine articles already accepted in sitemaps.
            return any(path in p and p.split(path,1)[1].strip('/') for path in c['paths'])
        return True
    if source=='cto':
        return p.count('/')<=2 and len(p.strip('/').split('-'))>=4 or p.startswith('/statistics/annual-reviews-prospects')
    return any(path in p for path in c['paths']) and not p.endswith('/feed/')

def audit_one(source, max_sitemaps=35):
    db=connect(); c=SOURCES[source]; f=Fetcher(source,db)
    audit=dict(name=c['name'],access=c['access'],terms=c['terms'],note=c['note'],errors=[],sitemaps=[],archive_links=0)
    audit['retryable_errors']=False
    print(json.dumps(dict(event='audit_start',source=source)),flush=True)
    try:
        robots=f.robots()
        audit['robots_status']=f.robot_status
        audit['robots_text']=robots
    except Exception as e:
        if isinstance(e,StopRequested):db.close();raise
        audit['robots_status']=f.robot_status or 'unavailable';audit['errors'].append(str(e))
        audit['retryable_errors']=isinstance(e,FetchError) and e.retryable
        record_audit(db,source,audit);db.close();return source,audit
    # Source restriction checks deliberately precede automated content discovery.
    if c['access']!='public_research_review':
        audit['discovery_status']='held_for_authorization_or_source_verification'
        record_audit(db,source,audit);db.close();return source,audit
    seeds=re.findall(r'^Sitemap:\s*(\S+)',robots,re.I|re.M)
    if not seeds:
        seeds=[c['base']+'/sitemap.xml',c['base']+'/sitemap_index.xml',c['base']+'/wp-sitemap.xml']
    version=fingerprint(ROOT/'research/discover.py',ROOT/'research/config.py')
    key='discovery_frontier:'+source
    previous=db.execute('SELECT * FROM checkpoints WHERE name=?',(key,)).fetchone()
    saved=json.loads(previous['payload']) if previous and previous['fingerprint']==version else {}
    queue=saved.get('queue',list(seeds));visited=set(saved.get('visited',[]))
    audit['sitemaps']=saved.get('sitemaps',[])
    audit['errors']=saved.get('permanent_errors',[])
    failed=[];processed=0
    def save_frontier():
        checkpoint(db,key,version,'progress',dict(queue=queue+failed,visited=sorted(visited),
            sitemaps=audit['sitemaps'],permanent_errors=[e for e in audit['errors'] if e not in transient_messages]))
    transient_messages=[]
    while queue and processed<max_sitemaps:
        check_stop(DATA,source)
        url=queue.pop(0)
        if url in visited:continue
        processed+=1
        try:
            data,meta=f.fetch(url,'sitemap')
            if data[:2]==b'\x1f\x8b':data=gzip.decompress(data)
            root=etree.fromstring(data,parser=etree.XMLParser(resolve_entities=False,no_network=True))
            kind=etree.QName(root).localname
            if kind not in ('sitemapindex','urlset'):raise ValueError('Expected sitemap XML, received '+kind)
            locations=root.xpath('//*[local-name()="loc"]/text()')
            audit['sitemaps'].append(dict(url=url,kind=kind,locations=len(locations)))
            if kind=='sitemapindex':
                queue.extend(x for x in locations if x not in visited)
            elif kind=='urlset':
                for node in root:
                    loc=node.xpath('./*[local-name()="loc"]/text()')
                    mod=node.xpath('./*[local-name()="lastmod"]/text()')
                    if loc and content_url(source,loc[0]):
                        add_url(db,source,loc[0],url,mod[0] if mod else '')
                db.commit()
            visited.add(url)
        except Exception as e:
            if isinstance(e,StopRequested):db.close();raise
            message=url+': '+str(e);audit['errors'].append(message)
            if isinstance(e,FetchError) and e.retryable:
                failed.append(url);transient_messages.append(message);audit['retryable_errors']=True
            else:visited.add(url)
            exception('sitemap_failed',source=source,url=url,error=str(e))
        save_frontier()
        if f.stopped:break
    queue+=failed
    audit['remaining_sitemaps']=queue
    if not f.stopped:
        for route in c['archives']:
            url=urljoin(c['base'],route)
            try:
                data,meta=f.fetch(url,'archive')
                soup=BeautifulSoup(data,'lxml')
                links=[]
                for a in soup.find_all('a',href=True):
                    link=urldefrag(urljoin(meta['final_url'],a['href']))[0]
                    if content_url(source,link):
                        add_url(db,source,link,url,hint_title=a.get_text(' ',strip=True))
                        links.append(link)
                audit['archive_links']+=len(set(links)); db.commit()
            except Exception as e:
                if isinstance(e,StopRequested):db.close();raise
                audit['errors'].append(url+': '+str(e))
                if isinstance(e,FetchError) and e.retryable:audit['retryable_errors']=True
                exception('archive_seed_failed',source=source,url=url,error=str(e))
                if f.stopped:break
    audit['discovered_urls']=db.execute('SELECT COUNT(*) FROM urls WHERE source=?',(source,)).fetchone()[0]
    audit['discovery_status']='inventory_incomplete' if queue or audit['errors'] else 'sitemaps_and_seed_archives_processed'
    record_audit(db,source,audit);db.close()
    print(json.dumps(dict(event='audit_done',source=source,urls=audit['discovered_urls'],errors=len(audit['errors']))),flush=True)
    return source,audit

def main():
    p=argparse.ArgumentParser();p.add_argument('--sources',nargs='+',default=list(SOURCES));p.add_argument('--max-sitemaps',type=int,default=35)
    a=p.parse_args();results={}
    # Initialize schema/WAL before concurrent worker connections.
    bootstrap=connect();bootstrap.close()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(audit_one,s,a.max_sitemaps):s for s in a.sources}
        for ft in as_completed(futures):
            s=futures[ft]
            try:results[s]=ft.result()[1]
            except Exception as e:results[s]={'error':str(e)}
    OUTPUT.mkdir(exist_ok=True)
    db=connect()
    all_audits={r['source']:json.loads(r['payload']) for r in db.execute('SELECT source,payload FROM audit')}
    (OUTPUT/'source_audit.json').write_text(json.dumps(all_audits,indent=2,ensure_ascii=False),'utf-8')
    print(json.dumps({s:{k:v for k,v in d.items() if k in ('access','discovered_urls','robots_status','discovery_status','error')} for s,d in results.items()},indent=2))

if __name__=='__main__':main()
