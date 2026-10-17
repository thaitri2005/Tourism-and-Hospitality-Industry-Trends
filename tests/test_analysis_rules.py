from types import SimpleNamespace

from research.codebook import brand_hits, org_hits, theme_hits
from research.discover import content_url


def themes(text):
    return set(theme_hits(text))


def test_ai_is_case_sensitive_and_not_part_of_other_words():
    assert 'Artificial intelligence' not in themes('Thailand welcomes visitors to its islands. The aim is growth.')
    assert 'Artificial intelligence' in themes('Hotels are adopting AI tools.')
    assert 'Artificial intelligence' in themes('Generative AI and machine learning change distribution.')


def test_overlapping_terms_count_once():
    hits = theme_hits('Generative AI is spreading.')['Artificial intelligence']
    assert [m.group() for m in hits] == ['Generative AI']


def test_multiple_themes_allowed():
    found = themes('Investment in workforce education and climate action.')
    assert {'Workforce, skills & education', 'Sustainability & climate', 'Investment & hotel development'} <= found


def test_ambiguous_words_are_not_themes():
    assert 'Air, cruise & connectivity' not in themes('The programme trains hotel staff.')
    assert 'Distribution, OTAs & loyalty' not in themes('The European Travel Commission published a report.')
    assert 'Workforce, skills & education' not in themes('Labour Day holiday bookings increased.')
    assert 'Travel demand & economic performance' not in themes('Booking.com offers a reservation system.')


def test_specific_concepts():
    assert 'Digital technology & data' in themes('A software provider introduced property management systems.')
    assert 'Travel demand & economic performance' in themes('Travel intentions and booking momentum increased.')
    assert 'Sustainability & climate' in themes('Community ecotourism supports wildlife conservation.')
    assert 'COVID-19 pandemic' in themes('Hotels reopened after COVID-19 lockdowns.')
    assert 'Social media & digital marketing' in themes('The campaign used TikTok influencers.')


def brands(text):
    return set(brand_hits(text))


def test_brand_word_boundaries_and_homonyms():
    assert 'Hilton' in brands('Hilton announced results')
    assert 'Hilton' not in brands('Hiltonshire is a fictional name')
    assert 'Hilton' not in brands('Paris Hilton visited the resort.')
    assert 'Hilton' not in brands('Golf at Hilton Head Island.')
    assert 'Carnival' not in brands('Carnival in Bissau is a cultural festival.')
    assert 'Carnival' in brands('Carnival Corporation presented its results. Carnival also announced plans.')
    assert 'Four Seasons' not in brands('Travel experiences for all four seasons.')
    assert 'Four Seasons' in brands('The CEO of Four Seasons attended.')
    assert 'Emirates' not in brands('The United Arab Emirates welcomed delegates.')
    assert 'Emirates' in brands('Emirates and British Airways participated.')
    assert 'Mews' not in brands('The street of mews houses is attractive.')
    assert 'Mews' in brands('Mews announced new hotel software.')


def test_str_needs_benchmarking_context():
    assert 'STR' in brands('STR data show occupancy rose.')
    assert 'STR' not in brands('Cities regulate STR listings and STRs.')


def test_sub_brands_and_longest_name_win():
    found = brand_hits('Hampton by Hilton and the Ritz-Carlton opened.')
    assert set(found) == {'Hampton', 'Ritz-Carlton'}


def test_organisations():
    assert 'WTTC' in org_hits('The World Travel & Tourism Council (WTTC) said.')
    assert 'IATA' not in org_hits('Iata is not an acronym here.')


def test_article_coding_uses_headline_and_lead(monkeypatch):
    from research import analyze
    monkeypatch.setattr(analyze, 'SCORER', lambda texts: {t: (0.1, 0.2, 0.7) for t in texts})
    row = SimpleNamespace(doc_id='d1', source='wttc', title='Hotels bet on artificial intelligence at Hilton',
                          body='Hotels bet on artificial intelligence\nGuests liked the service. Revenue was strong. ' * 3)
    themes_rows, brand_rows, org_rows, _ = analyze.code_article(row)
    analyze.score_rows(themes_rows + brand_rows)
    ai = next(r for r in themes_rows if r['theme'] == 'Artificial intelligence')
    assert ai['in_title'] and ai['discussed']
    assert ai['sentiment'] == 0.6 and ai['sentiment_label'] == 'positive'
    assert brand_rows[0]['brand'] == 'Hilton' and brand_rows[0]['sentiment_label'] == 'positive'


def test_footer_lines_do_not_create_social_media_theme():
    from research.analyze import clean_text
    _, text = clean_text('News', 'The hotel opened.\nFollow us on Facebook, Twitter and Instagram\nwww.example.com')
    assert 'Facebook' not in text


def test_foreign_routes_are_not_english_candidates():
    assert not content_url('untourism', 'https://www.untourism.int/fr/news/example')
    assert content_url('untourism', 'https://www.untourism.int/news/example')


def test_trusted_news_archive_recovers_legacy_paths_without_broadening_sitemaps():
    for path in ['/new/measurement', '/node/10047', '/global/older-article', '/flat-legacy-slug']:
        url = 'https://www.untourism.int'+path
        assert content_url('untourism', url, from_news_archive=True)
        assert not content_url('untourism', url)
    for url in ['https://www.untourism.int/archive/global/', 'https://www.untourism.int/news',
                'https://www.untourism.int/fr/news/example', 'https://www.untourism.int/image.png',
                'https://outside.example/news/article']:
        assert not content_url('untourism', url, from_news_archive=True)


def test_archived_article_is_distinct_from_archive_index():
    for path in ['/archive/global/news/2017-12-07/old-article', '/archive/asia/press-release/2017-12-18/old-release']:
        url = 'https://www.untourism.int'+path
        assert content_url('untourism', url)
        assert content_url('untourism', url, from_news_archive=True)
    for path in ['/archive/global/', '/archive/global/news/', '/archive/asia/press-release/']:
        assert not content_url('untourism', 'https://www.untourism.int'+path, from_news_archive=True)
