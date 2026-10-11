from research.extract import extract_html,normalize_date,language

def test_published_is_not_modified():
    html=b'''<html lang="en"><meta property="article:published_time" content="2018-06-12"><meta property="article:modified_time" content="2026-01-02"><h1>Research article</h1><div class="details-block__lead-paragraph"><p>'''+b'The tourism sector and the environment are important. '*35+b'</p></div></html>'
    d,_=extract_html('wttc','https://wttc.org/news/example',html,{})
    assert d['published_at']=='2018-06-12'
    assert d['modified_at']=='2026-01-02'
    assert d['eligible']==1

def test_missing_date_not_inferred_from_current_year():
    assert normalize_date('May 4')==''
    assert normalize_date('12.11.2019')=='2019-11-12'

def test_gated_pdf_not_ordinary_download():
    html=b'''<html lang="en"><meta property="article:published_time" content="2020-01-01"><h1>Report</h1><a href="#" data-document-url="https://etc-corporate.org/uploads/report.pdf">Download</a><section class="page-res"><div class="p18 text-justify">'''+b'The report considers tourism and the environment. '*20+b'</div></section></html>'
    d,links=extract_html('etc','https://etc-corporate.org/reports/report/',html,{})
    assert d['content_type']=='report_summary'
    assert links[0]['gated'] is True
    assert 'summary_not_full_report' in d['quality_flags']

def test_outside_window_and_language_excluded():
    html=b'<html lang="fr"><meta property="article:published_time" content="2015-01-01"><h1>Old</h1><article>Texte</article></html>'
    d,_=extract_html('untourism','https://www.untourism.int/news/old',html,{})
    assert d['eligible']==0
    assert 'outside_window' in d['exclusion_reason']
    assert 'not_verified_english' in d['exclusion_reason']

def test_english_html_does_not_override_spanish_body():
    text='El turismo en el país y los viajes de las personas son una parte de la economía. '*20
    assert language(text,'en')[0]=='es'
    assert language('The hotels and the airlines are investing in the region for the future. '*20,'en')[0]=='en'

def test_contacts_and_boilerplate_removed():
    html=b'<html lang="en"><h1>News</h1><meta property="article:published_time" content="2020-01-01"><div class="details-block__lead-paragraph"><p>'+b'The tourism industry is investing in new hotels and jobs. '*30+b'</p><p>For media enquiries, please contact Example Person</p><p>About WTTC:</p><p>Boilerplate text.</p></div></html>'
    d,_=extract_html('wttc','https://wttc.org/news/example',html,{})
    assert 'Example Person' not in d['body']
    assert 'Boilerplate text' not in d['body']


def test_pdf_link_returning_html_is_retained_but_excluded():
    html=b'<html lang="en"><meta property="article:published_time" content="2021-05-24"><h1>Home</h1><article>'+b'The tourism industry is investing in new hotels and jobs. '*30+b'</article></html>'
    d,_=extract_html('untourism','https://www.untourism.int/old-report.pdf',html,{})
    assert d['word_count']>=120
    assert d['eligible']==0
    assert d['exclusion_reason']=='unexpected_html_for_pdf'
