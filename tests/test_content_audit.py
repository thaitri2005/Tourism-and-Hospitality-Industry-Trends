import hashlib
import pandas as pd
from research import content_audit as audit
from research.extract import extract_html


def article(body,source='pata',title='Airport operations',extra=''):
    html=('<html lang="en"><meta property="article:published_time" content="2020-01-02">'
          '<h1>'+title+'</h1><article><div class="blog-item-content e-content">'+body+'</div>'+extra+'</article></html>').encode()
    record,_=extract_html(source,'https://www.pata.org/blog/test',html,{})
    return record,html


def test_pata_article_body_excludes_author_categories_and_adjacent_story():
    body='<p>'+('The airport team has a plan for visitors and their journeys. '*15)+'</p>'
    doc,_=article(body,extra='<div class="blog-item-author-profile-wrapper">Marketing PATA Associate</div>'
                         '<div class="blog-meta-item--tags">Sustainability</div><nav>Next AI robotics story</nav>')
    assert 'Marketing' not in doc['body'] and 'Sustainability' not in doc['body']
    assert 'AI robotics' not in doc['body'] and doc['eligible']==1


def test_legal_and_resource_pages_do_not_become_news():
    for title in ['Mobile Texting: Terms and Conditions','Resources']:
        doc,_=article('The conditions of this service apply to the users of the website. '*20,title=title)
        assert not doc['eligible'] and 'non_article_page' in doc['exclusion_reason']


def test_raw_audit_detects_invented_body_and_structured_date_conflict():
    doc,raw=article('The airport team has a plan for visitors. '*30)
    good=audit.raw_review(doc,raw,{})
    assert good['raw_body_support']==1 and good['date_check']=='structured_support'
    doc.update(body='Completely unrelated fabricated phrase nobody actually published. '*30,published_at='2021-02-03')
    bad=audit.raw_review(doc,raw,{})
    assert bad['raw_body_support']==0 and bad['date_check']=='structured_conflict'


def test_source_balancing_exposes_small_source_sensitivity():
    theme='Sustainability, climate and nature'
    core=pd.DataFrame([dict(doc_id=str(i),source='large' if i<100 else 'small',published_at='2026-01-01') for i in range(101)])
    tags=pd.DataFrame([dict(doc_id='100',source='small',theme=theme)])
    rows=audit.rank_scenarios(core,tags,'2025-10-11')
    shares={r['scenario']:r['share_pct'] for r in rows if r['theme']==theme}
    assert shares['equal_source_all']==50 and shares['equal_source_min20']==0
    assert 0<shares['article_weighted']<1


class NeutralSentiment:
    def polarity_scores(self,text):return {'compound':0}


def test_focus_incidental_mentions_and_career_context_are_distinguished():
    doc,_=article('The survey describes bookings for hotels. '+('The results describe the activities for visitors. '*35)+
                  ' The spokesperson mentioned sustainability once. Its team brings experience from Wyndham and other firms.',
                  title='Hotel bookings rise')
    result=audit.semantic_review(doc,NeutralSentiment())
    assert any(r['theme']=='Demand, performance and recovery' for r in result['gaps'])
    sustainability=next(r for r in result['themes'] if r['theme']=='Sustainability, climate and nature')
    assert sustainability['focus_status']=='incidental_or_uncertain'
    entity=next(r for r in result['entities'] if r['entity']=='Wyndham')
    assert entity['context_type']=='career_history_present'


def test_vendored_sentiment_resource_is_pinned():
    assert hashlib.sha256(audit.RESOURCE.read_bytes()).hexdigest()==audit.EXPECTED_LEXICON


def test_post_extraction_curation_is_narrow_and_idempotent():
    from research.curate import curate_record
    doc,_=article('The training programme supports the people and the industry. '*30,title='International',source='ahla')
    doc['url']='https://www.ahla.com/news/international'
    corrected=curate_record(doc)
    assert not corrected['eligible'] and corrected['exclusion_reason']=='non_article_page'
    assert curate_record(corrected)==corrected
    doc['url']='https://www.ahla.com/news/international-travel-recovery'
    assert curate_record(doc)['eligible']==1
    doc,_=article('The training programme supports the people and the industry. '*30+'\nBack to Blog Homepage >\nMarketing PATA Associate')
    corrected=curate_record(doc)
    assert 'Back to Blog' not in corrected['body'] and 'Marketing' not in corrected['body']
    assert corrected['word_count']<doc['word_count'] and corrected['content_hash']!=doc['content_hash']
    assert curate_record(corrected)==corrected


def test_hospitality_main_content_excludes_company_boilerplate_and_tags():
    from research.curate import curate_record
    body='The hotel has introduced a new guest service for the people who visit. '*15
    doc,_=article(body+'\nAbout Hilton\nHilton sustainability marketing',source='hospitalitynet')
    raw=('<article><header>A headline</header><section aria-label="Main content">'+body+
         '</section><section class="boilerplate">About Hilton</section>'
         '<section aria-label="Tags">AI Marketing</section></article>').encode()
    corrected=curate_record(doc,raw)
    assert corrected['body']==body.strip()
    assert 'Hilton' not in corrected['body'] and 'Marketing' not in corrected['body']
    assert corrected['eligible']==1
    assert curate_record(corrected,raw)==corrected
