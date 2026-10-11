"""Exercise actual numerical models in small, deterministic offline fixtures."""
import json
import numpy as np
import pandas as pd
import pytest
from research import analyze

@pytest.fixture
def model_output(tmp_path,monkeypatch):
    monkeypatch.setattr(analyze,'OUTPUT',tmp_path)
    monkeypatch.setattr(analyze,'TABLES',tmp_path/'tables')
    return tmp_path

def test_nmf_trains_on_distinct_topics_and_exports_finite_weights(model_output):
    topics=['carbon renewable emissions conservation energy forest',
            'software algorithms artificial intelligence automation robotics',
            'workers training wages careers recruitment employment',
            'investment lending finance assets equity capital',
            'culture heritage museums traditions festivals monuments']
    noise=['regional','local','international','urban','coastal','rural','island','mountain']
    data=pd.DataFrame([dict(doc_id=str(i),source='wttc',year=2020,
                            body=' '.join([topics[i%5]]*10+[noise[i%8],noise[(i*3+2)%8]]),
                            url=f'https://example.org/{i}') for i in range(50)])
    result=analyze.topic_model(data)
    weights=pd.read_csv(model_output/'tables'/'nmf_assignments.csv')
    assert len(result)==5 and len(weights)==50
    assert np.isfinite(weights.weight).all()
    assert weights.cluster.nunique()==5
    assert json.loads((model_output/'nmf_model_metadata.json').read_text())['status']=='exploratory_unreviewed'

def test_unusable_topic_vocabulary_has_an_explicit_skip_status(model_output):
    data=pd.DataFrame([dict(body='the and travel tourism industry') for _ in range(25)])
    assert analyze.topic_model(data).empty
    assert json.loads((model_output/'nmf_model_metadata.json').read_text())['status']=='insufficient_vocabulary'

def test_exact_duplicates_still_work_when_near_duplicate_vocabulary_is_empty(model_output):
    data=pd.DataFrame([dict(doc_id=str(i),content_hash='same',body='the and of',word_count=3) for i in range(8)])
    result=analyze.de_duplicate(data)
    assert result.story_id.nunique()==1
    assert json.loads((model_output/'deduplication_metadata.json').read_text())['near_duplicate_search']=='insufficient_vocabulary'
