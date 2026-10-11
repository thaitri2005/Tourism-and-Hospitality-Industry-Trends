from research.codebook import tag_themes,entity_patterns,entity_matches
from research.discover import content_url

def test_ai_is_not_part_of_thailand():
    assert 'AI and digital technology' not in tag_themes('Thailand welcomes visitors to its islands.')
    assert 'AI and digital technology' in tag_themes('Hotels are adopting AI tools.')

def test_multiple_themes_allowed():
    tags=tag_themes('Investment in workforce education and climate action.')
    assert 'Workforce, skills and education' in tags
    assert 'Sustainability, climate and nature' in tags
    assert 'Investment, infrastructure and development' in tags

def test_foreign_routes_are_not_english_candidates():
    assert not content_url('untourism','https://www.untourism.int/fr/news/example')
    assert content_url('untourism','https://www.untourism.int/news/example')


def test_trusted_news_archive_recovers_legacy_paths_without_broadening_sitemaps():
    for path in ['/new/measurement','/node/10047','/global/older-article','/flat-legacy-slug']:
        url='https://www.untourism.int'+path
        assert content_url('untourism',url,from_news_archive=True)
        assert not content_url('untourism',url)
    for url in ['https://www.untourism.int/archive/global/',
                'https://www.untourism.int/news',
                'https://www.untourism.int/fr/news/example',
                'https://www.untourism.int/image.png',
                'https://outside.example/news/article']:
        assert not content_url('untourism',url,from_news_archive=True)


def test_archived_article_is_distinct_from_archive_index():
    for path in ['/archive/global/news/2017-12-07/old-article',
                 '/archive/asia/press-release/2017-12-18/old-release']:
        url='https://www.untourism.int'+path
        assert content_url('untourism',url)
        assert content_url('untourism',url,from_news_archive=True)
    for path in ['/archive/global/','/archive/global/news/','/archive/asia/press-release/']:
        assert not content_url('untourism','https://www.untourism.int'+path,from_news_archive=True)

def test_brand_word_boundaries():
    p=next(p for name,kind,p in entity_patterns() if name=='Hilton')
    assert p.search('Hilton announced results')
    assert not p.search('Hiltonshire is a fictional name')


def matched_brand(name,text):
    p=next(p for n,kind,p in entity_patterns() if n==name)
    return entity_matches(name,p,text)


def test_brand_homonyms_from_corpus_review():
    assert not matched_brand('Carnival','Carnival in Bissau is a cultural festival.')
    assert matched_brand('Carnival','Carnival Corporation presented its results. Carnival also announced plans.')
    assert matched_brand('Carnival',"Carnival, the world's largest cruise operators offered ships.")
    assert not matched_brand('Intrepid','A destination for intrepid travellers.')
    assert matched_brand('Intrepid','Intrepid Travel announced plans.')
    assert not matched_brand('Four Seasons','Travel experiences for all four seasons.')
    assert matched_brand('Four Seasons','The CEO of Four Seasons attended.')


def test_emirates_brand_country_and_government_body():
    assert not matched_brand('Emirates','The United Arab Emirates welcomed delegates.')
    assert not matched_brand('Emirates','Emirates Council for Balanced Development joined.')
    assert matched_brand('Emirates','Emirates and British Airways participated.')


def test_extracted_headline_is_not_counted_twice():
    from research.analyze import analysis_text
    assert analysis_text('Hilton announces plans','Back\nHilton announces plans\nThe article.')=='Back Hilton announces plans The article.'
    assert analysis_text('Hilton announces plans','The article.')=='Hilton announces plans. The article.'
