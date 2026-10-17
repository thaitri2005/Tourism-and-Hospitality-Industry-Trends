"""Sentence sentiment with a RoBERTa model, cached so each sentence is scored once.

Model: cardiffnlp/twitter-roberta-base-sentiment-latest (Loureiro et al., 2022),
three classes (negative / neutral / positive). On the 120-sentence validation
sample it agreed with the independent reading for 85% of sentences, against 56%
for the VADER lexicon (see research/resources/validation_sentiment.csv).

Scores are stored in data/sentiment_cache.sqlite keyed by a hash of the sentence
and the model revision; reruns only score new sentences. Model weights are
downloaded once to tmp/hf (about 500 MB). The first full run scores roughly
10-15 sentences per second on a laptop CPU.
"""
import hashlib
import os
import sqlite3
import time

from .config import DATA, ROOT
from .runtime import event, check_stop

MODEL = 'cardiffnlp/twitter-roberta-base-sentiment-latest'
REVISION = '3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7'
LABELS = ('negative', 'neutral', 'positive')
BATCH, MAX_TOKENS = 32, 128

_model = None


def _key(text):
    return hashlib.sha256((REVISION + '\n' + text).encode('utf-8')).hexdigest()


def _cache():
    DATA.mkdir(exist_ok=True)
    db = sqlite3.connect(DATA/'sentiment_cache.sqlite', timeout=60)
    db.execute('CREATE TABLE IF NOT EXISTS scores (key TEXT PRIMARY KEY, negative REAL, neutral REAL, positive REAL)')
    return db


def _load():
    global _model
    if _model is None:
        os.environ.setdefault('HF_HOME', str(ROOT/'tmp'/'hf'))
        os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
        model = AutoModelForSequenceClassification.from_pretrained(MODEL, revision=REVISION).eval()
        _model = (torch, tokenizer, model)
    return _model


def probabilities(texts):
    """{text: (p_negative, p_neutral, p_positive)} for every distinct text."""
    texts = sorted(set(texts), key=len)   # length-sorted batches waste little padding
    db = _cache()
    found = {}
    keys = {t: _key(t) for t in texts}
    for i in range(0, len(texts), 500):
        chunk = [keys[t] for t in texts[i:i+500]]
        rows = db.execute(f'SELECT key,negative,neutral,positive FROM scores WHERE key IN ({",".join("?"*len(chunk))})', chunk)
        found.update({k: (n, u, p) for k, n, u, p in rows})
    todo = [t for t in texts if keys[t] not in found]
    if todo:
        torch, tokenizer, model = _load()
        started = time.monotonic()
        event('sentiment_scoring_started', sentences=len(todo), cached=len(texts)-len(todo), model=MODEL)
        with torch.inference_mode():
            for i in range(0, len(todo), BATCH):
                check_stop(DATA)
                batch = todo[i:i+BATCH]
                encoded = tokenizer(batch, padding=True, truncation=True, max_length=MAX_TOKENS, return_tensors='pt')
                probs = model(**encoded).logits.softmax(-1).tolist()
                rows = [(keys[t],)+tuple(p) for t, p in zip(batch, probs)]
                db.executemany('INSERT OR REPLACE INTO scores VALUES (?,?,?,?)', rows)
                db.commit()   # an interrupted run keeps every finished batch
                found.update({k: (n, u, p) for k, n, u, p in rows})
                if (i // BATCH) % 100 == 99:
                    rate = (i+BATCH)/(time.monotonic()-started)
                    event('sentiment_progress', scored=i+BATCH, of=len(todo), per_second=round(rate, 1),
                          minutes_left=round((len(todo)-i-BATCH)/rate/60, 1))
    db.close()
    return {t: found[keys[t]] for t in texts}


def summarise(probs):
    """Mean class probabilities -> (score in -1..1, label)."""
    n = len(probs)
    mean = [sum(p[k] for p in probs)/n for k in range(3)]
    return mean[2]-mean[0], LABELS[max(range(3), key=lambda k: mean[k])]
