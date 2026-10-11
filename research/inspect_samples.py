import json
from bs4 import BeautifulSoup
from .store import connect
from .http import Fetcher

def main():
    db=connect()
    samples={
      'wttc': ['https://wttc.org/news/wttc-unveils-safe-travels-new-global-protocols-to-restart-the-travel-tourism-sector'],
      'etc': ['https://etc-corporate.org/news/etc-publishes-new-quarterly-report-7/',
              'https://etc-corporate.org/reports/european-tourism-2016-trends-prospects-q3-2016/']}
    for source,urls in samples.items():
        f=Fetcher(source,db);f.robots()
        for url in urls:
            try:data,meta=f.fetch(url,'extraction_sample')
            except Exception as e:
                print('ERROR',url,str(e),flush=True);continue
            soup=BeautifulSoup(data,'lxml')
            print('\nURL',url)
            print('META',[(m.get('name') or m.get('property'),m.get('content')) for m in soup.find_all('meta') if any(w in str(m).lower() for w in ['date','published','modified','language'])])
            print('JSONLD',[s.get_text()[:5500] for s in soup.select('script[type="application/ld+json"]')])
            h=soup.find('h1')
            if h:
                print('H1 PARENTS',[(p.name,p.get('class'),p.get('id')) for p in list(h.parents)[:5]])
            for sel in ['article','main','.entry-content','.post-content','.news-detail','.news-content']:
                x=soup.select_one(sel)
                if x:print('SELECTOR',sel,len(x.get_text()),x.get_text(' ',strip=True)[:2200])
            print('PDF',[(a.get_text(' ',strip=True),a['href']) for a in soup.select('a[href]') if '.pdf' in a['href'].lower()][:12])
if __name__=='__main__':main()
