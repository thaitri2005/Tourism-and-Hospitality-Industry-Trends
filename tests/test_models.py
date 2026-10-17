"""Exercise the numerical models in small, deterministic offline fixtures."""
from collections import Counter

import numpy as np
import pandas as pd

from research import analyze


def test_nmf_finds_distinct_topics():
    topics = ['carbon renewable emissions conservation energy forest',
              'software algorithms artificial intelligence automation robotics',
              'workers training wages careers recruitment employment',
              'investment lending finance assets equity capital',
              'culture heritage museums traditions festivals monuments']
    noise = ['regional', 'local', 'international', 'urban', 'coastal', 'rural', 'island', 'mountain']
    data = pd.DataFrame([dict(doc_id=str(i), source='wttc', year=2020 + i % 3, title=f'Story {i}',
                              body=' '.join([topics[i % 5]]*10 + [noise[i % 8], noise[(i*3+2) % 8]])) for i in range(250)])
    result, years, dominant = analyze.topic_model(data, k=5)
    assert len(result) == 5 and result.articles.sum() == 250
    assert result.articles.min() >= 40
    assert np.isfinite(years.share_pct).all() and len(dominant) == 250


def test_topic_model_skips_tiny_corpora():
    result, years, dominant = analyze.topic_model(pd.DataFrame([dict(title='a', body='b', source='wttc', year=2020)]*5))
    assert result.empty and years.empty


def test_exact_and_near_duplicates_share_a_story():
    base = 'The tourism ministry announced a new visa policy for international visitors arriving by air. ' * 8
    data = pd.DataFrame([dict(doc_id='a', content_hash='h1', body=base, word_count=120),
                         dict(doc_id='b', content_hash='h1', body=base, word_count=120),
                         dict(doc_id='c', content_hash='h2', body=base + ' Updated.', word_count=121),
                         dict(doc_id='d', content_hash='h3', body='Completely different text about hotel food waste. ' * 10, word_count=70)]
                        + [dict(doc_id=f'x{i}', content_hash=f'x{i}', body=f'unrelated filler story number {i} about airports and cruise ships ' * 5,
                                word_count=45) for i in range(4)])
    result = analyze.de_duplicate(data)
    story = dict(zip(result.doc_id, result.story_id))
    assert story['a'] == story['b'] == story['c']
    assert story['d'] != story['a']


def test_equal_source_weighting_ignores_volume():
    cells = pd.DataFrame([dict(source='big', year=2020, theme='T', articles=1000, discussing=100, share_pct=10.0, in_yearly_comparison=True),
                          dict(source='small', year=2020, theme='T', articles=20, discussing=10, share_pct=50.0, in_yearly_comparison=True),
                          dict(source='tiny', year=2020, theme='T', articles=5, discussing=5, share_pct=100.0, in_yearly_comparison=False)])
    pooled = analyze.equal_source(cells, ['year'])
    assert pooled.share_pct.iloc[0] == 30.0
    assert pooled.sources.iloc[0] == 2


def test_log_odds_prefers_words_overrepresented_in_target():
    target = Counter({'airline': 40, 'hotel': 10, 'guest': 5})
    background = Counter({'airline': 50, 'hotel': 400, 'guest': 300, 'room': 200})
    assert analyze.log_odds_terms(target, background, top=1, minimum=1) == ['airline']
