import hashlib
import io
import json
import re
import warnings
from datetime import datetime
from urllib.parse import urljoin,urlparse,urldefrag
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date
from pypdf import PdfReader
from .config import START,END,SOURCES

MONTHS=r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
DATE_RE=re.compile(r'\b(?:\d{1,2}(?:st|nd|rd|th)?\s+'+MONTHS+r'\s*,?\s*20\d{2}|'+MONTHS+r'\s+\d{1,2}(?:st|nd|rd|th)?\s*,?\s*20\d{2}|\d{1,2}\.\d{1,2}\.20\d{2})\b',re.I)

def normalize_date(value):
    if not value or not re.search(r'\b(?:19|20)\d{2}\b',str(value)):return ''
    try:
        text=str(value).strip()
        # Never use the execution machine's year/day as a missing-date default.
        return parse_date(text,default=datetime(1900,1,1),dayfirst=bool(re.match(r'^\d{1,2}\.\d{1,2}\.',text))).date().isoformat()
    except (ValueError,TypeError,OverflowError):return ''

def walk_json(value):
    if isinstance(value,dict):
        yield value
        for v in value.values():yield from walk_json(v)
    elif isinstance(value,list):
        for v in value:yield from walk_json(v)

def language(text,html_lang=''):
    lang=(html_lang or '').lower().split('-')[0]
    words=re.findall(r'[a-z]+',text.lower())
    en={'the','and','of','to','in','that','for','with','is','are','on','as','by','from','will','this','be','their','has','have'}
    fr={'le','la','les','de','du','des','et','en','est','une','un','pour','dans','qui','que','sur','avec','au','aux','nous','ses','ces'}
    es={'el','la','los','las','de','del','y','en','es','una','un','para','que','con','por','se','su','sus','como','al','ha','han'}
    scores={name:sum(w in vocab for w in words)/max(len(words),1) for name,vocab in [('en',en),('fr',fr),('es',es)]}
    # Page language metadata has been observed to mislabel translated content.
    # Verify the body rather than blindly trusting lang="en".
    if lang and lang!='en':return lang,'html_lang_nonenglish'
    if scores['en']>=.08 and scores['en']>=1.2*max(scores['fr'],scores['es']):
        return 'en','body_stopwords_verified'+('_html_en' if lang=='en' else '')
    strongest=max(scores,key=scores.get)
    return (strongest if strongest!='en' and scores[strongest]>=.1 else 'unknown'),'body_language_heuristic_metadata_not_trusted'

def make_record(source,url,title,body,published,modified,evidence,confidence,lang,kind,flags,meta,author='',publisher=''):
    body=re.sub(r'[ \t]+',' ',body).strip()
    wc=len(re.findall(r'\b\w+\b',body))
    reasons=[]
    if not published:reasons.append('publication_date_unresolved')
    elif published<START or published>END:reasons.append('outside_window')
    if lang!='en':reasons.append('not_verified_english')
    minimum=60 if kind=='report_summary' else 120
    if wc<minimum:reasons.append('insufficient_text')
    if not title:reasons.append('missing_title')
    if 'unexpected_html_for_pdf' in flags:reasons.append('unexpected_html_for_pdf')
    if re.fullmatch(r'(?:mobile texting:\s*)?terms(?:\s+(?:and|&)\s+conditions|\s+of\s+use)|privacy policy|resources|contact(?: us)?',title.strip(),re.I):
        flags.append('non_article_page');reasons.append('non_article_page')
    norm=re.sub(r'\W+',' ',body.lower()).strip()
    digest=hashlib.sha256(norm.encode()).hexdigest()
    return dict(doc_id=hashlib.sha256(url.encode()).hexdigest()[:20],source=source,url=url,canonical_url=url,
        title=title,published_at=published,modified_at=modified,date_evidence=evidence,date_confidence=confidence,
        language=lang,content_type=kind,body=body,word_count=wc,content_hash=digest,
        raw_path='',retrieved_at=meta.get('retrieved_at',''),quality_flags=json.dumps(flags),eligible=int(not reasons),
        exclusion_reason=';'.join(reasons),publisher=publisher or SOURCES[source]['name'],author=author,duplicate_cluster=digest)

def extract_html(source,url,data,meta,hints=None):
    hints=hints or {}; soup=BeautifulSoup(data,'lxml');flags=[]
    # A broken PDF link may return an HTTP-200 homepage/login page. Retain the
    # response for audit, but never treat its text/date as the requested report.
    if urlparse(url).path.lower().endswith('.pdf'):
        flags.append('unexpected_html_for_pdf')
    ld=[]
    for s in soup.select('script[type="application/ld+json"]'):
        try:ld.extend(walk_json(json.loads(s.get_text())))
        except (ValueError,TypeError):flags.append('invalid_jsonld')
    candidates=[v for v in ld if 'datePublished' in v]
    candidates.sort(key=lambda v:0 if v.get('@type') in ('Article','NewsArticle','BlogPosting') else 1)
    candidate=candidates[0] if candidates else {}
    h1=soup.find('h1')
    title=h1.get_text(' ',strip=True) if h1 else candidate.get('headline','')
    if not title and soup.title:title=soup.title.get_text(' ',strip=True)
    metadata={m.get('property') or m.get('name'):m.get('content','') for m in soup.find_all('meta')}
    published=normalize_date(metadata.get('article:published_time') or candidate.get('datePublished'))
    modified=normalize_date(metadata.get('article:modified_time') or candidate.get('dateModified'))
    evidence='structured_datePublished' if published else '';confidence='high' if published else 'unresolved'
    if not published:
        published_time=soup.select_one('.field--field-published time[datetime]')
        if published_time:
            published=normalize_date(published_time.get('datetime'))
            if published:evidence='publisher_datetime_field';confidence='high'
    selectors={
        'wttc':['.details-block__lead-paragraph','.details-block','article','main'],
        'etc':['.page-res .p18.text-justify','.p18.text-justify','section.regular.page-res','section.regular'],
        'untourism':['.field--name-body','.field-name-body','article','main'],
        'cto':['.entry-content','.wp-block-post-content','article','main'],
        'ihra':['.entry-content','.post-content','article','main'],
        'pata':['.blog-item-content.e-content','.entry-content','.post-content','article','main'],
        'ahla':['.field--name-body','.node__content','article','main'],
        'hospitalitynet':['.hn-article__content','.article-content','.article__content','article','main'],
        'travelweekly':['.article-body','.article__body','.article-content','article','main']}
    root=None;selector=''
    for sel in selectors.get(source,['article','main']):
        nodes=soup.select(sel)
        if nodes:
            root=max(nodes,key=lambda n:len(n.get_text(' ',strip=True)));selector=sel;break
    if root is None:
        root=soup.body or soup;flags.append('fallback_body_extractor')
    # Store report links before removing forms; gated download controls are only
    # inventoried, never submitted or bypassed.
    links=[]
    for a in root.select('a[href]'):
        href=urldefrag(urljoin(url,a['href']))[0]
        if '.pdf' in urlparse(href).path.lower():links.append(dict(url=href,gated=False,label=a.get_text(' ',strip=True)))
    for a in soup.select('[data-document-url]'):
        links.append(dict(url=urljoin(url,a['data-document-url']),gated=True,label=a.get('data-document-title','')))
    for n in root.select('script,style,nav,footer,form,aside,.related-items,.social-share,.breadcrumbs,.cookie-notice'):
        n.decompose()
    body=root.get_text('\n',strip=True)
    # Remove recurring publisher/contact sections without removing the article's
    # substantive discussion of the publisher.
    body=re.split(r'\n(?:About WTTC\s*:?|About the World Travel & Tourism Council\s*:?|Media [Cc]ontact(?:s)?\s*:?|Press [Cc]ontact(?:s)?\s*:?|Notes to [Ee]ditors\s*:?)\s*\n',body)[0]
    body=re.split(r'\n(?:For media enquiries|For more information about WTTC|Contacts?\s*:|UNWTO Communications(?:\s|&)|Tel\s*:\s*\(\+34\)|Follow us on\s*\n)',body,flags=re.I)[0]
    if source=='untourism':body=re.split(r'\n(?:Related|Useful) [Ll]inks\s*:?\s*\n',body)[0]
    if source in ('pata','ahla','hospitalitynet'):
        body=re.split(r'\n(?:About PATA|About (?:the )?Pacific Asia Travel Association|About AHLA|About (?:the )?American Hotel\s*(?:&|and)\s*Lodging Association)\s*:?\s*\n',body,flags=re.I)[0]
    if not published:
        visible=root.get_text(' ',strip=True)
        date_match=DATE_RE.search(visible[:6000])
        if date_match:
            published=normalize_date(date_match.group());evidence='visible_date:'+date_match.group();confidence='medium';flags.append('visible_date_needs_review')
        elif hints.get('hint_date'):
            published=normalize_date(hints['hint_date']);evidence='archive_or_parent:'+hints.get('discovered_via','');confidence='medium';flags.append('inherited_date')
    html=soup.find('html');lang,lang_evidence=language(body,html.get('lang','') if html else '')
    flags.extend(['extractor:'+selector,'language:'+lang_evidence])
    kind='report_summary' if '/reports/' in url or '/reports-insights/' in url else ('blog' if '/blog/' in url else 'news')
    if kind=='report_summary':flags.append('summary_not_full_report')
    if any(x['gated'] for x in links):flags.append('report_download_form_not_submitted')
    def name(v):
        if isinstance(v,dict):return v.get('name','')
        if isinstance(v,list):return '; '.join(name(x) for x in v)
        return str(v or '')
    result=make_record(source,url,title,body,published,modified,evidence,confidence,lang,kind,flags,meta,name(candidate.get('author')),name(candidate.get('publisher')))
    canonical=soup.select_one('link[rel="canonical"]')
    if canonical:result['canonical_url']=urljoin(url,canonical.get('href',url))
    return result,links

def extract_pdf(source,url,data,meta,hints=None):
    hints=hints or {}
    reader=PdfReader(io.BytesIO(data));parts=[];flags=['pdf_layout_not_fully_reviewed']
    for page in reader.pages:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore');parts.append(page.extract_text() or '')
    body='\n\n'.join(parts)
    title=hints.get('hint_title') or str((reader.metadata or {}).get('/Title','')) or urlparse(url).path.rsplit('/',1)[-1]
    published=normalize_date(hints.get('hint_date'))
    evidence='parent_landing_page:'+hints.get('discovered_via','') if published else ''
    confidence='medium' if published else 'unresolved'
    if not published:
        match=DATE_RE.search(body[:2500])
        if match:
            published=normalize_date(match.group());evidence='pdf_front_matter:'+match.group();confidence='medium';flags.append('pdf_visible_date_needs_review')
    # PDF creation/modification dates are deliberately NOT treated as publication dates.
    lang,le=language(body[:30000]);flags.append('language:'+le)
    if len(body)<100:flags.append('ocr_required')
    flags.append('pdf_pages:'+str(len(reader.pages)))
    kind='news_pdf' if re.search(r'press[ _-]*release|(?:^|[/_])pr[_-]',url,re.I) or re.search(r'PRESS\s+RELEASE',body[:500]) else 'report_pdf'
    if kind=='news_pdf':body=re.split(r'\n(?:Media [Cc]ontacts?|For (?:further|more) information|Notes to [Ee]ditors)',body)[0]
    return make_record(source,url,title,body,published,'',evidence,confidence,lang,kind,flags,meta)
