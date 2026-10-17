"""Validation sample: compare the automated coding with an independent reading.

``python -m research.validation sample`` draws a stratified random sample of
analysable articles and theme sentences and writes a reading packet to
tmp/validation/ (local only: it contains publisher text). Without seeing the
automated coding, the reader records

* the themes each article is substantially about, in resources/validation_themes.csv
  (doc_id, source, reader_themes separated by "; "), and
* the tone of each sampled sentence, in resources/validation_sentiment.csv
  (sentence_id, doc_id, source, vader_compound, model_label, reader_label).

analyze.py scores the current coding against these labels on every run.
"""
import argparse
import hashlib
import random
import sqlite3

import pandas as pd

from .codebook import THEMES, theme_hits
from .config import DATA, END, ROOT, START

PACKET = ROOT/'tmp'/'validation'
THEME_LABELS = ROOT/'research'/'resources'/'validation_themes.csv'
SENTIMENT_LABELS = ROOT/'research'/'resources'/'validation_sentiment.csv'
PER_SOURCE, SENTENCES_PER_SOURCE, SEED = 8, 15, 20261017


def candidates():
    db = sqlite3.connect((DATA/'corpus.sqlite').as_uri()+'?mode=ro', uri=True)
    df = pd.read_sql_query("""SELECT doc_id, source, title, body, published_at FROM documents
        WHERE eligible=1 AND content_type IN ('news','blog','news_pdf') AND published_at BETWEEN ? AND ?""", db, params=(START, END))
    db.close()
    return df


def sample():
    from .analyze import SENTENCE, VADER, clean_text, label
    df = candidates().sort_values('doc_id')
    rng = random.Random(SEED)
    articles, sentences = [], []
    for source, group in df.groupby('source'):
        rows = group.to_dict('records')
        rng.shuffle(rows)
        articles += rows[:PER_SOURCE]
        pool = []
        for row in rows[PER_SOURCE:PER_SOURCE+200]:
            title, text = clean_text(row['title'], row['body'])
            for s in SENTENCE.split(text):
                if 40 <= len(s) <= 400 and theme_hits(s):
                    pool.append((row, s))
        rng.shuffle(pool)
        for row, s in pool[:SENTENCES_PER_SOURCE]:
            compound = VADER.polarity_scores(s)['compound']
            sentences.append(dict(sentence_id=hashlib.sha256(s.encode()).hexdigest()[:12], doc_id=row['doc_id'], source=source,
                                  vader_compound=round(compound, 4), vader_label=label(compound), text=s))
    from .sentiment import probabilities, summarise
    probs = probabilities([s['text'] for s in sentences])
    for s in sentences:
        s['model_label'] = summarise([probs[s['text']]])[1]
    PACKET.mkdir(parents=True, exist_ok=True)
    lines = ['# Validation reading packet', '', 'Themes: ' + '; '.join(THEMES), '']
    for row in articles:
        title, text = clean_text(row['title'], row['body'])
        lines += [f'## {row["doc_id"]} | {row["source"]} | {row["published_at"]}', f'**{title}**', ' '.join(text.split()[:300]), '']
    (PACKET/'articles.md').write_text('\n'.join(lines), 'utf-8')
    lines = ['# Sentence tone packet (label positive / neutral / negative)', '']
    lines += [f'{s["sentence_id"]} | {s["source"]} | {s["text"]}' for s in sentences]
    (PACKET/'sentences.md').write_text('\n'.join(lines), 'utf-8')
    pd.DataFrame(sentences).drop(columns=['text', 'vader_label']).to_csv(PACKET/'sentences.csv', index=False)
    print(f'{len(articles)} articles and {len(sentences)} sentences written to {PACKET}')


def score(themes, analysed_ids):
    """Precision/recall of the automated theme coding and VADER agreement against the reader's labels."""
    if not THEME_LABELS.is_file():
        return None, None
    labels = pd.read_csv(THEME_LABELS, encoding='utf-8-sig').fillna('')
    labels = labels[labels.doc_id.isin(set(analysed_ids))]
    rows = []
    for rule in ('discussed', 'mentioned'):
        coded = themes if rule == 'mentioned' else themes[themes.discussed]
        for theme in THEMES:
            tp = fp = fn = 0
            for r in labels.itertuples():
                truth = theme in {t.strip() for t in r.reader_themes.split(';') if t.strip()}
                auto = bool(((coded.doc_id == r.doc_id) & (coded.theme == theme)).any())
                tp += truth and auto
                fp += auto and not truth
                fn += truth and not auto
            rows.append(dict(rule=rule, theme=theme, reader_positive=tp+fn, true_positive=tp, false_positive=fp, false_negative=fn))
    by_theme = pd.DataFrame(rows)
    by_theme['precision'] = by_theme.true_positive/(by_theme.true_positive+by_theme.false_positive).replace(0, float('nan'))
    by_theme['recall'] = by_theme.true_positive/(by_theme.true_positive+by_theme.false_negative).replace(0, float('nan'))
    summary = [dict(measure='articles', value=len(labels)), dict(measure='per_website', value=PER_SOURCE)]
    for rule in ('discussed', 'mentioned'):
        t = by_theme[by_theme.rule == rule][['true_positive', 'false_positive', 'false_negative']].sum()
        p, r = t.true_positive/max(t.true_positive+t.false_positive, 1), t.true_positive/max(t.true_positive+t.false_negative, 1)
        prefix = '' if rule == 'discussed' else 'mention_'
        summary += [dict(measure=prefix+'precision', value=p), dict(measure=prefix+'recall', value=r),
                    dict(measure=prefix+'f1', value=2*p*r/max(p+r, 1e-9))]
    if SENTIMENT_LABELS.is_file():
        from .analyze import label
        s = pd.read_csv(SENTIMENT_LABELS, encoding='utf-8-sig')
        s['vader_label'] = s.vader_compound.map(label)
        summary += [dict(measure='sentiment_items', value=len(s)),
                    dict(measure='sentiment_agreement', value=(s.model_label == s.reader_label).mean()),
                    dict(measure='vader_agreement', value=(s.vader_label == s.reader_label).mean())]
        for cls in ('positive', 'neutral', 'negative'):
            summary.append(dict(measure=f'reader_{cls}', value=int((s.reader_label == cls).sum())))
            hit = s[s.model_label == cls]
            summary.append(dict(measure=f'model_{cls}_precision', value=(hit.reader_label == cls).mean() if len(hit) else float('nan')))
            found = s[s.reader_label == cls]
            summary.append(dict(measure=f'model_{cls}_recall', value=(found.model_label == cls).mean() if len(found) else float('nan')))
    return pd.DataFrame(summary), by_theme


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['sample'])
    parser.parse_args()
    sample()
