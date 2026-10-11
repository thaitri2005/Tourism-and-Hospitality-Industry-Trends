"""Build transparent preliminary outputs from a snapshot of locally collected text."""
import argparse
from collections import Counter,defaultdict
import json
import platform
import re
import warnings
import os
import textwrap
from pathlib import Path
from .config import ROOT,DATA,OUTPUT,SOURCES,START,END
os.environ['MPLCONFIGDIR']=str(ROOT/'tmp'/'matplotlib')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import TfidfVectorizer,ENGLISH_STOP_WORDS
from sklearn.decomposition import NMF
from sklearn.neighbors import NearestNeighbors
from textblob import TextBlob
from .store import connect,now
from .codebook import THEMES,BRANDS,ORGANIZATIONS,tag_themes,entity_patterns,entity_matches,ENTITY_DISAMBIGUATION
from .runtime import event,atomic_json

TABLES=OUTPUT/'tables';FIGURES=OUTPUT/'figures'

def csv(df,name):
    TABLES.mkdir(parents=True,exist_ok=True)
    df.to_csv(TABLES/name,index=False,encoding='utf-8-sig')

def safe_md(value):return str(value).replace('|','/').replace('\n',' ')


def analysis_text(title,body):
    # Some source selectors already include the headline. Counting it again
    # inflates name/keyword frequency and gives its sentiment extra weight.
    title=re.sub(r'\s+',' ',title).strip()
    body=re.sub(r'\s+',' ',body).strip()
    return body if not title or title.casefold() in body.casefold() else title+'. '+body

def table_md(df,columns,limit=20):
    lines=['| '+' | '.join(columns)+' |','| '+' | '.join(['---']*len(columns))+' |']
    for _,r in df.head(limit).iterrows():lines.append('| '+' | '.join(safe_md(r[c]) for c in columns)+' |')
    return '\n'.join(lines)

def de_duplicate(df):
    # Exact normalized-body duplicates first. Near duplicates are connected at
    # >=0.94 TF-IDF cosine similarity and similar length. Keep the pair evidence.
    df=df.copy();parent=list(range(len(df)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    pairs=[];hashes={}
    for i,h in enumerate(df.content_hash):
        if h in hashes:parent[i]=find(hashes[h]);pairs.append((i,hashes[h],1.0,'exact'))
        else:hashes[h]=i
    near_status='insufficient_documents'
    if len(df)>5:
        vect=TfidfVectorizer(min_df=2,max_features=25000,ngram_range=(1,2),stop_words='english')
        try:
            x=vect.fit_transform(df.body.fillna(''))
        except ValueError as exc:
            if not any(word in str(exc).lower() for word in ['vocabulary','terms remain']):raise
            x=None;near_status='insufficient_vocabulary'
            event('near_duplicate_search_skipped',level='WARNING',reason=str(exc))
    else:x=None
    if x is not None:
        near_status='completed'
        nn=NearestNeighbors(metric='cosine',algorithm='brute',n_neighbors=min(6,len(df))).fit(x)
        distances,indices=nn.kneighbors(x)
        lengths=df.word_count.to_numpy()
        for i,(ds,js) in enumerate(zip(distances,indices)):
            for dist,j in zip(ds,js):
                if j>=i or dist>.06:continue
                if min(lengths[i],lengths[j])/max(lengths[i],lengths[j],1)<.75:continue
                parent[find(i)]=find(j);pairs.append((i,int(j),float(1-dist),'near'))
    groups={}
    for i in range(len(df)):
        root=find(i);groups.setdefault(root,df.iloc[root].doc_id)
    df['story_id']=[groups[find(i)] for i in range(len(df))]
    out=[dict(doc_a=df.iloc[i].doc_id,doc_b=df.iloc[j].doc_id,similarity=round(score,4),method=method) for i,j,score,method in pairs]
    csv(pd.DataFrame(out,columns=['doc_a','doc_b','similarity','method']),'duplicate_pairs.csv')
    atomic_json(OUTPUT/'deduplication_metadata.json',dict(documents=len(df),exact_hash_search='completed',
        near_duplicate_search=near_status,similarity_threshold=.94,max_neighbours=6))
    return df

def heatmap(matrix,path,title,fmt='.0f',vmax=None):
    if matrix.empty:return
    fig,ax=plt.subplots(figsize=(max(9,matrix.shape[1]*.8),max(5,matrix.shape[0]*.42+2)))
    values=matrix.to_numpy(dtype=float)
    cmap=plt.colormaps['YlGnBu'].with_extremes(bad='#e4e7eb')
    im=ax.imshow(np.ma.masked_invalid(values),aspect='auto',cmap=cmap,vmin=0,vmax=vmax)
    ax.set_xticks(range(matrix.shape[1]),matrix.columns,rotation=35,ha='right')
    ax.set_yticks(range(matrix.shape[0]),matrix.index)
    ax.set_title(textwrap.fill(title,width=48),pad=20,loc='left',fontweight='bold')
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v=values[i,j]
            if not np.isnan(v):
                lim=vmax if vmax is not None else np.nanmax(values)
                ax.text(j,i,format(v,fmt),ha='center',va='center',fontsize=8,color='white' if v>lim*.6 else '#142b3a')
    fig.colorbar(im,ax=ax,shrink=.65,pad=.025)
    fig.text(.01,.012,'Exploratory collected corpus. Grey = no observations. 2016 and 2026 cover partial years.',fontsize=9,color='#52606d')
    fig.tight_layout(rect=(0,.045,1,1));fig.savefig(path,dpi=170);plt.close(fig)

def topic_model(core):
    empty=pd.DataFrame(columns=['cluster','documents_dominant','top_terms','example_urls'])
    def skipped(reason):
        csv(empty,'discovered_topics_nmf.csv')
        csv(pd.DataFrame(columns=['doc_id','cluster','weight']),'nmf_assignments.csv')
        atomic_json(OUTPUT/'nmf_model_metadata.json',dict(status=reason,documents=len(core)))
        event('topic_model_skipped',level='WARNING',reason=reason,documents=len(core))
        return empty
    if len(core)<20:return skipped('insufficient_documents')
    stop=set(ENGLISH_STOP_WORDS)|{'tourism','travel','industry','sector','wttc','unwto','said','council','world','commission','european','etc','mr','ms','www','http','https','org','com','download','press','release','new','also'}
    stop|={'pdf','related','links','pr','tel','fax','communications','back','previous','read','view'}
    v=TfidfVectorizer(stop_words=sorted(stop),min_df=3,max_df=.8,max_features=24000,ngram_range=(1,2),sublinear_tf=True,token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z-]+\b')
    try:
        x=v.fit_transform(core.body)
    except ValueError as exc:
        if not any(word in str(exc).lower() for word in ['vocabulary','terms remain']):raise
        return skipped('insufficient_vocabulary')
    if x.shape[1]<2:return skipped('insufficient_vocabulary')
    k=min(15,max(5,len(core)//30),x.shape[1]-1)
    # Limit training contributions from each source/year without throwing away
    # documents when applying the trained model.
    sampled=core.groupby(['source','year'],group_keys=False).sample(frac=1,random_state=42).groupby(['source','year']).head(70).index
    positions=core.index.get_indexer(sampled)
    k=min(k,len(positions))
    model=NMF(n_components=k,init='nndsvda',random_state=42,max_iter=450)
    model.fit(x[positions]);weights=model.transform(x)
    words=np.array(v.get_feature_names_out());rows=[];assignment=[]
    for i,component in enumerate(model.components_):
        ids=np.argsort(weights[:,i])[-5:][::-1]
        rows.append(dict(cluster=i+1,top_terms='; '.join(words[np.argsort(component)[-12:][::-1]]),documents_dominant=int((weights.argmax(axis=1)==i).sum()),example_urls=' | '.join(core.iloc[ids].url)))
    for i,row in enumerate(core.itertuples()):
        assignment.append(dict(doc_id=row.doc_id,cluster=int(weights[i].argmax())+1,weight=float(weights[i].max())))
    result=pd.DataFrame(rows);csv(result,'discovered_topics_nmf.csv');csv(pd.DataFrame(assignment),'nmf_assignments.csv')
    (OUTPUT/'nmf_model_metadata.json').write_text(json.dumps(dict(method='TF-IDF + NMF',components=k,training_documents=len(positions),applied_documents=len(core),random_state=42,iterations=int(model.n_iter_),status='exploratory_unreviewed'),indent=2),'utf-8')
    return result

def main():
    TABLES.mkdir(parents=True,exist_ok=True);FIGURES.mkdir(parents=True,exist_ok=True)
    db=connect();docs=pd.read_sql_query('SELECT * FROM documents',db);urls=pd.read_sql_query('SELECT * FROM urls',db)
    audits={r['source']:json.loads(r['payload']) for r in db.execute('SELECT * FROM audit')};db.close()
    (OUTPUT/'source_audit.json').write_text(json.dumps(audits,indent=2,ensure_ascii=False),'utf-8')
    if docs.empty:raise ValueError('No documents collected; analysis cannot run. See source access and retry diagnostics.')
    docs['year']=pd.to_datetime(docs.published_at,errors='coerce').dt.year.astype('Int64')
    eligible=docs[docs.eligible==1].copy().reset_index(drop=True)
    eligible=de_duplicate(eligible)
    # Each source contributes at most one occurrence per unique story per year.
    core=eligible[eligible.content_type.isin(['news','blog','news_pdf'])].sort_values('published_at').drop_duplicates(['source','year','story_id']).reset_index(drop=True)
    if core.empty:raise ValueError('No eligible English articles with usable publication dates; review extraction/coverage diagnostics before analysis.')
    supplements=eligible[~eligible.content_type.isin(['news','blog','news_pdf'])].copy()
    metadata=docs.drop(columns=['body','raw_path'])
    csv(metadata,'document_metadata.csv');csv(urls,'url_inventory.csv')
    csv(core.drop(columns=['body','raw_path']),'core_article_metadata.csv')
    csv(supplements.drop(columns=['body','raw_path']),'report_metadata.csv')
    # Local research text is retained in SQLite, not bundled into public-facing exports.
    csv(pd.DataFrame([dict(source=s,name=c['name'],source_class=c['group'],access_status=c['access'],robots_status=audits.get(s,{}).get('robots_status','not_checked'),discovered=int((urls.source==s).sum()),extracted=int((docs.source==s).sum()),eligible=int((eligible.source==s).sum()),core_unique_occurrences=int((core.source==s).sum()),report_records=int((supplements.source==s).sum()),remaining=int(((urls.source==s)&urls.status.isin(['discovered','retry_wait','in_progress'])).sum()),note=c['note'],terms=c['terms']) for s,c in SOURCES.items()]),'source_coverage.csv')
    csv(docs.groupby(['source','exclusion_reason'],dropna=False).size().reset_index(name='documents'),'exclusions.csv')
    counts=core.groupby(['source','year']).size().reset_index(name='articles')
    csv(counts,'coverage_by_source_year.csv')
    rows=[];entity_rows=[];association_rows=[];sentiment_rows=[];patterns=entity_patterns()
    print(json.dumps({'event':'analyze_start','extracted':len(docs),'eligible':len(eligible),'core':len(core),'reports':len(supplements)}),flush=True)
    for i,row in enumerate(core.itertuples()):
        text=analysis_text(row.title,row.body)
        themes=tag_themes(text)
        # Score each theme-containing sentence once, then reuse that score for
        # its themes. This avoids scoring overlapping context windows repeatedly.
        sentence_scores=defaultdict(list)
        for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z“\"])',text):
            sentence_themes=tag_themes(sentence)
            if sentence_themes:
                polarity=float(TextBlob(sentence).sentiment.polarity)
                for theme in sentence_themes:sentence_scores[theme].append(polarity)
        for theme,hits in themes.items():
            evidence=sorted(set(m.group().lower() for m in hits))
            rows.append(dict(doc_id=row.doc_id,source=row.source,year=row.year,date=row.published_at,theme=theme,matched_terms='; '.join(evidence),match_count=len(hits)))
            # Sentence polarity is only a weak aspect proxy, not a validated
            # target-specific sentiment or stance model.
            scores=sentence_scores.get(theme) or [0.0]
            positive=any(x>.1 for x in scores);negative=any(x<-.1 for x in scores)
            label='mixed' if positive and negative else ('positive' if positive else ('negative' if negative else 'neutral'))
            sentiment_rows.append(dict(doc_id=row.doc_id,source=row.source,year=row.year,theme=theme,label=label,mean_polarity=round(float(np.mean(scores)),4),status='unvalidated_lexicon_baseline'))
        for name,kind,pattern in patterns:
            matches=entity_matches(name,pattern,text)
            if not matches:continue
            entity_rows.append(dict(doc_id=row.doc_id,source=row.source,year=row.year,entity=name,entity_type=kind,mentions=len(matches),url=row.url))
            nearby=set()
            for m in matches:nearby.update(tag_themes(text[max(0,m.start()-350):min(len(text),m.end()+350)]))
            if kind=='brand_name_family':
                for theme in nearby:association_rows.append(dict(doc_id=row.doc_id,brand=name,theme=theme,source=row.source,year=row.year,method='within_350_characters_of_name',url=row.url))
        if (i+1)%300==0:print(json.dumps({'event':'coded','articles':i+1}),flush=True)
    tags=pd.DataFrame(rows,columns=['doc_id','source','year','date','theme','matched_terms','match_count']);entities=pd.DataFrame(entity_rows,columns=['doc_id','source','year','entity','entity_type','mentions','url'])
    associations=pd.DataFrame(association_rows,columns=['doc_id','brand','theme','source','year','method','url'])
    sentiment=pd.DataFrame(sentiment_rows,columns=['doc_id','source','year','theme','label','mean_polarity','status'])
    csv(tags,'theme_assignments.csv');csv(entities,'entity_mentions.csv');csv(associations,'brand_theme_evidence.csv');csv(sentiment,'sentiment_unvalidated.csv')
    yearly=[]
    for (s,y),g in core.groupby(['source','year']):
        sub=tags[(tags.source==s)&(tags.year==y)]
        for t in THEMES:
            n=int((sub.theme==t).sum());yearly.append(dict(source=s,year=y,theme=t,articles=n,denominator=len(g),share_pct=round(100*n/len(g),2),small_sample=len(g)<20,partial_year=y in [2016,2026]))
    annual=pd.DataFrame(yearly);csv(annual,'themes_by_source_year.csv')
    profiles=[]
    for s,g in core.groupby('source'):
        for t in THEMES:
            n=int(((tags.source==s)&(tags.theme==t)).sum());profiles.append(dict(source=s,theme=t,articles=n,denominator=len(g),share_pct=round(100*n/len(g),2)))
    profiles=pd.DataFrame(profiles);csv(profiles,'themes_by_source.csv')
    current=core[core.published_at>='2025-10-11'];current_tags=tags[tags.doc_id.isin(current.doc_id)]
    current_rows=[]
    for t in THEMES:
        sub=current_tags[current_tags.theme==t];source_shares=[]
        for s,g in current.groupby('source'):source_shares.append(100*int((sub.source==s).sum())/len(g))
        current_rows.append(dict(theme=t,articles=len(sub),denominator=len(current),article_share_pct=round(100*len(sub)/max(len(current),1),2),equal_source_share_pct=round(float(np.mean(source_shares)),2) if source_shares else 0,sources_mentioning=int(sub.source.nunique())))
    current_ranking=pd.DataFrame(current_rows).sort_values(['equal_source_share_pct','articles'],ascending=False);csv(current_ranking,'current_theme_ranking.csv')
    brand_ranking=entities.groupby(['entity','entity_type']).agg(documents=('doc_id','nunique'),sources=('source','nunique'),mentions=('mentions','sum')).reset_index().sort_values('documents',ascending=False)
    csv(brand_ranking,'entity_ranking.csv')
    if not associations.empty:
        a=associations.groupby(['brand','theme']).agg(documents=('doc_id','nunique')).reset_index()
        brand_counts=entities[entities.entity_type=='brand_name_family'].groupby('entity').doc_id.nunique()
        theme_counts=tags.groupby('theme').doc_id.nunique()
        a['brand_documents']=a.brand.map(brand_counts);a['theme_documents']=a.theme.map(theme_counts)
        a['association_share_pct']=100*a.documents/a.brand_documents
        a['lift']=(a.documents*len(core)/(a.brand_documents*a.theme_documents)).round(3)
        a['low_support']=a.documents<3
        csv(a.sort_values('documents',ascending=False),'brand_theme_associations.csv')
    else:
        csv(pd.DataFrame(columns=['brand','theme','documents','brand_documents','theme_documents','association_share_pct','lift','low_support']),'brand_theme_associations.csv')
    sentiment_summary=sentiment.groupby(['theme','label']).size().reset_index(name='documents')
    csv(sentiment_summary,'sentiment_summary_unvalidated.csv')
    topics=topic_model(core)
    topic_status=json.loads((OUTPUT/'nmf_model_metadata.json').read_text('utf-8'))['status']
    matrix=counts.pivot(index='source',columns='year',values='articles').reindex(index=list(SOURCES),columns=range(2016,2027))
    heatmap(matrix,FIGURES/'coverage.png','Eligible news/blog articles by source and year')
    heatmap(profiles.pivot(index='theme',columns='source',values='share_pct'),FIGURES/'themes_by_source.png','Exploratory theme mentions by source (%)',vmax=100)
    for source in core.source.unique():
        matrix=annual[annual.source==source].pivot(index='theme',columns='year',values='share_pct').reindex(columns=range(2016,2027))
        heatmap(matrix,FIGURES/f'themes_over_time_{source}.png',SOURCES[source]['name']+' - exploratory theme mentions (%)',vmax=100)
    # Reproducible sample for actual human validation; empty review fields do not
    # count as completed validation.
    validation=pd.concat([g.sample(min(3,len(g)),random_state=42) for _,g in core.groupby(['source','year'])],ignore_index=True)
    validation=validation[[c for c in ['doc_id','source','year','url','title','published_at','date_confidence','word_count'] if c in validation.columns]]
    for col in ['reviewer','date_correct','body_correct','topic_review','entity_review','notes']:validation[col]=''
    csv(validation,'human_review_template.csv')
    (OUTPUT/'theme_codebook.json').write_text(json.dumps(dict(version='0.2',status='exploratory_unvalidated',rules=THEMES,brands=BRANDS,organizations=ORGANIZATIONS,entity_disambiguation=ENTITY_DISAMBIGUATION),indent=2,ensure_ascii=False),'utf-8')
    snapshot=dict(created_at=now(),window_start=START,window_end=END,current_window_start='2025-10-11',extracted_documents=len(docs),eligible_documents=len(eligible),core_articles=len(core),unique_story_clusters=int(core.story_id.nunique()),report_records=len(supplements),current_articles=len(current),active_sources=sorted(core.source.unique()),complete_sources=0,unprocessed_candidates=int(urls.status.isin(['discovered','retry_wait','in_progress']).sum()),python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,validation_status='automated checks and limited extraction spot checks; independent human coding not completed')
    (OUTPUT/'run_summary.json').write_text(json.dumps(snapshot,indent=2),'utf-8')
    coverage=pd.read_csv(TABLES/'source_coverage.csv')
    report=['# Tourism and hospitality discourse: preliminary collection and analysis',
      '\nSnapshot: '+snapshot['created_at']+'. Requested window: '+START+' through '+END+'. English only.',
      '\n**This is an incomplete, exploratory corpus, not a completed nine-source industry study.** Counts below describe successfully collected eligible records. Unavailable sources are not zero-discussion sources.',
      f'\nCollected {len(docs):,} documents; {len(eligible):,} pass date/language/length checks. The primary analysis uses {len(core):,} news/blog article occurrences after within-source/year deduplication; {len(supplements):,} report summaries/PDF records are kept separately. Current-window articles: {len(current):,}.',
      '\n## Source coverage\n',table_md(coverage,['source','access_status','extracted','core_unique_occurrences','report_records','remaining'],20),
      '\n![Coverage](figures/coverage.png)',
      '\n## Ten leading current candidate themes\nThese are ranked mentions of a predefined 14-concept codebook, not ten independently validated discoveries. One article can match multiple concepts. Equal-source shares prevent the largest collected source from dominating; this does not repair missing sources. Current window: 11 October 2025 through 10 October 2026.\n',
      table_md(current_ranking.round(1),['theme','articles','article_share_pct','equal_source_share_pct','sources_mentioning'],10),
      '\n## Themes by year and website\nThe CSV `themes_by_source_year.csv` includes numerator, denominator, small-sample flags, and partial-year flags. Compare years within sources first. The available sources and archive depth differ. No industry-wide historical trend is claimed.\n',
      '\n![Source themes](figures/themes_by_source.png)',
      *['\n![Annual themes '+s+'](figures/themes_over_time_'+s+'.png)' for s in core.source.unique()],
      '\n## Brands and organizations\nDictionary-based name-family matches are exploratory and non-exhaustive. Corporate ownership and formal partnerships are not inferred. Brand-topic associations use a local 350-character context and need semantic review.\n',
      table_md(brand_ranking[brand_ranking.entity_type=='brand_name_family'],['entity','documents','sources'],15),
      '\n## Independent topic discovery\nTF-IDF/NMF provides a separate discovery check. Terms below require human labeling; geographic clusters and communication formats can appear alongside substantive themes. Model status: '+topic_status+'. A skipped model has no inferred topic results.\n',
      table_md(topics,['cluster','documents_dominant','top_terms'],15),
      '\n## Sentiment\n`sentiment_unvalidated.csv` and its summary are an optional TextBlob lexicon baseline on theme-related contexts. They have not been validated on this domain and must not be reported as reliable industry attitudes. Mixed positive/negative contexts are retained. Publisher promotional tone and incomplete coverage remain major limitations.',
      '\n## What remains\nPublisher authorization/export arrangements for PATA, AHLA, Hospitality Net, and Travel Weekly; verification of the IH&RA source; CTO access; full report access where downloads are gated; reconciliation of discovery coverage; broader manual extraction/date review; a held-out human-coded validation set; theme-codebook revision; and semantic review of brand associations.',
      '\n## Reproducibility and retention\nSource URLs, dates, extraction flags, exclusions, duplicate pairs, codebook, and model settings are exported under `tables/`. Full text remains in the local SQLite database and permitted raw cache, outside the shareable report. No messages were sent and no download forms were submitted. Each publisher retains its content rights.']
    (OUTPUT/'PRELIMINARY_REPORT.md').write_text('\n'.join(report),'utf-8')
    print(json.dumps(snapshot,indent=2),flush=True)

if __name__=='__main__':main()
