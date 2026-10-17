"""Answer the brief's four questions from the collected corpus.

1. The ten leading themes in the current discussion (last 12 months) and their sentiment.
2. How themes change year by year, 2016-2026, and which themes lead each year.
3. Each website's thematic focus.
4. Brand mentions, and the themes, sentiment and other brands associated with them.

Input: eligible documents in data/corpus.sqlite. Output (output/ or the staging
folder set by run.analyze_snapshot): tables/*.csv, figures/*.png, RESULTS.xlsx,
codebook.json and run_summary.json. Article text never leaves the database.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
import json
import math
import os
import platform
import re

from .config import ROOT, OUTPUT, SOURCES, START, END
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'tmp'/'matplotlib'))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import nltk.data
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

from .codebook import (BRANDS, BRAND_GROUP, CODEBOOK_VERSION, GBM_RANK, GBM_TOP10, ORGANIZATIONS, SOURCE_ORGANIZATION,
                       THEMES, brand_hits, org_hits, theme_hits)
from . import sentiment
from .runtime import atomic_json, event
from .store import connect, now

TABLES = OUTPUT/'tables'
FIGURES = OUTPUT/'figures'
CORE_TYPES = ('news', 'blog', 'news_pdf')
CURRENT_START = (date.fromisoformat(END) - timedelta(days=364)).isoformat()
MIN_CELL = 20          # articles needed for a source-year cell to enter yearly comparisons
MIN_BRAND = 15         # articles needed before a brand gets association/sentiment profiles
MAX_SENTENCES = 5      # sentences scored per article-theme and article-brand pair
LEAD_WORDS = 80        # the opening words that count as an article's lead
# NLTK resolves lexicons through its data path; the lexicon is vendored so no download is needed.
# VADER is only used to document the baseline in the validation sample (validation.py).
if str(ROOT/'research'/'resources') not in nltk.data.path:
    nltk.data.path.insert(0, str(ROOT/'research'/'resources'))
VADER = SentimentIntensityAnalyzer(lexicon_file='vader_lexicon.txt')
SCORER = sentiment.probabilities   # replaced by a stub in offline tests
SHORT = {'untourism': 'UN Tourism', 'wttc': 'WTTC', 'ihra': 'IH&RA', 'pata': 'PATA', 'ahla': 'AHLA', 'etc': 'ETC',
         'cto': 'CTO', 'hospitalitynet': 'Hospitality Net', 'travelweekly': 'Travel Weekly'}
SOURCE_TYPE = {'institution': 'Intergovernmental body', 'association': 'Industry association', 'trade_media': 'Trade media'}

# Footer/contact lines repeat platform names ("Follow us on Facebook") without discussing them.
FOOTER = re.compile(r'follow us|like us on|connect with us|(?:facebook|twitter|instagram|youtube|linkedin|tiktok)\.com|'
                    r'@[A-Za-z_][\w.]+|https?://|www\.|e-?mail\s*:|\btel\b\s*[:.+]|\bfax\b|phone\s*:|media contacts?|'
                    r'press contacts?|for more information|for further information|hashtags?\s*:|\bsource\s*:', re.I)
SENTENCE = re.compile(r'(?<=[.!?])\s+(?=[A-Z"“‘(\d])')
TOKEN = re.compile(r"[a-z][a-z'-]+[a-z]")
WORD = re.compile(r"[A-Za-z][A-Za-z'-]+[A-Za-z]")


# ---------------------------------------------------------------- utilities

def csv(df, name):
    TABLES.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES/name, index=False, encoding='utf-8-sig')
    return df


def label(compound):
    return 'positive' if compound >= .05 else ('negative' if compound <= -.05 else 'neutral')


def clean_text(title, body):
    lines = [line for line in (body or '').split('\n') if not (len(line) < 220 and FOOTER.search(line))]
    text = re.sub(r'\s+', ' ', ' '.join(lines)).strip()
    title = re.sub(r'\s+', ' ', title or '').strip()
    if title and text.casefold().startswith(title.casefold()):
        text = text[len(title):].lstrip(' .:-')
    return title, text


def de_duplicate(df):
    """Exact-hash duplicates, then near duplicates (TF-IDF cosine >= 0.94, similar length)."""
    df = df.copy().reset_index(drop=True)
    parent = list(range(len(df)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    first = {}
    for i, digest in enumerate(df.content_hash):
        if digest in first:
            parent[find(i)] = find(first[digest])
        else:
            first[digest] = i
    if len(df) > 5:
        matrix = TfidfVectorizer(min_df=2, max_features=30000, ngram_range=(1, 2), stop_words='english').fit_transform(df.body.fillna(''))
        distances, neighbours = NearestNeighbors(metric='cosine', n_neighbors=min(6, len(df))).fit(matrix).kneighbors(matrix)
        words = df.word_count.to_numpy()
        for i, (dist_row, idx_row) in enumerate(zip(distances, neighbours)):
            for dist, j in zip(dist_row, idx_row):
                if j < i and dist <= .06 and min(words[i], words[j]) / max(words[i], words[j], 1) >= .75:
                    parent[find(i)] = find(j)
    df['story_id'] = [df.doc_id.iloc[find(i)] for i in range(len(df))]
    return df


# ---------------------------------------------------------------- coding

def code_article(row):
    """Theme, brand and organisation evidence for one article.

    Sentiment is filled in later (score_rows), from up to MAX_SENTENCES sentences
    that mention the discussed theme or the brand, so the model runs in batches.
    """
    title, text = clean_text(row.title, row.body)
    sentences = [title] + [s for s in SENTENCE.split(text) if s.strip()] if title else SENTENCE.split(text)
    offsets, position = [], 0
    joined = ' \n '.join(sentences)
    for s in sentences:
        offsets.append(position)
        position += len(s) + 3
    lead_end = offsets[1] + len(' '.join(text.split()[:LEAD_WORDS])) if title and len(offsets) > 1 else len(' '.join(text.split()[:LEAD_WORDS]))
    title_end = len(title) if title else 0

    def sentence_of(pos):
        lo, hi = 0, len(offsets)-1
        while lo < hi:
            mid = (lo+hi+1)//2
            if offsets[mid] <= pos:
                lo = mid
            else:
                hi = mid-1
        return lo
    themes = theme_hits(joined)
    sentence_themes = defaultdict(set)
    theme_rows = []
    for theme, hits in themes.items():
        idx = sorted({sentence_of(m.start()) for m in hits})
        for i in idx:
            sentence_themes[i].add(theme)
        terms = {m.group().lower() for m in hits}
        in_title = any(m.start() < title_end for m in hits)
        lead = sum(1 for m in hits if title_end <= m.start() < lead_end)
        discussed = in_title or lead >= 2 or (len(hits) >= 3 and len(terms) >= 2)
        theme_rows.append(dict(doc_id=row.doc_id, theme=theme, mentions=len(hits), distinct_terms=len(terms), in_title=in_title,
                               lead_mentions=lead, discussed=discussed, sentences=len(idx), matched_terms='; '.join(sorted(terms)),
                               _texts=[sentences[i] for i in idx[:MAX_SENTENCES]] if discussed else []))
    brand_rows, windows = [], []
    for brand, hits in brand_hits(joined).items():
        idx = sorted({sentence_of(m.start()) for m in hits})
        window = sorted({j for i in idx for j in (i-1, i, i+1) if 0 <= j < len(sentences)})
        near = set().union(*(sentence_themes[j] for j in window))
        brand_rows.append(dict(doc_id=row.doc_id, brand=brand, group=BRAND_GROUP[brand] or brand, mentions=len(hits),
                               in_title=any(m.start() < title_end for m in hits), themes_nearby='; '.join(sorted(near)),
                               _texts=[sentences[i] for i in idx[:MAX_SENTENCES]]))
        windows.append((row.doc_id, brand, BRAND_GROUP[brand] or brand, ' '.join(sentences[j] for j in window)))
    org_rows = [dict(doc_id=row.doc_id, organization=name, mentions=len(hits)) for name, hits in org_hits(joined).items()
                if name != SOURCE_ORGANIZATION.get(row.source)]
    return theme_rows, brand_rows, org_rows, windows


def score_rows(rows):
    """Add sentiment (P(positive) - P(negative), -1..1) and its label to coded rows, in place."""
    probs = SCORER([t for r in rows for t in r['_texts']])
    for r in rows:
        texts = r.pop('_texts')
        r['sentiment'], r['sentiment_label'] = sentiment.summarise([probs[t] for t in texts]) if texts else (np.nan, None)
        if texts:
            r['sentiment'] = round(r['sentiment'], 4)


# ---------------------------------------------------------------- aggregation helpers

def theme_cells(core, discussed):
    """Share of each source-year cell's articles that discuss each theme."""
    n = core.groupby(['source', 'year']).size().rename('articles').reset_index()
    k = discussed.groupby(['source', 'year', 'theme']).size().rename('discussing')
    grid = n.merge(pd.DataFrame({'theme': list(THEMES)}), how='cross')
    grid = grid.merge(k.reset_index(), on=['source', 'year', 'theme'], how='left').fillna({'discussing': 0})
    grid['discussing'] = grid.discussing.astype(int)
    grid['share_pct'] = 100*grid.discussing/grid.articles
    grid['in_yearly_comparison'] = grid.articles >= MIN_CELL
    return grid


def equal_source(cells, by):
    """Mean of within-source shares, so no single website dominates a pooled figure."""
    used = cells[cells.in_yearly_comparison]
    out = used.groupby(by+['theme']).agg(share_pct=('share_pct', 'mean'), sources=('source', 'nunique'),
                                         articles=('articles', 'sum'), discussing=('discussing', 'sum')).reset_index()
    out['article_weighted_pct'] = 100*out.discussing/out.articles
    return out


def log_odds_terms(target_counts, background_counts, top=12, minimum=6, prior=10000):
    """Distinctive words: z-scored log-odds ratio with an informative Dirichlet prior (Monroe et al., 2008).

    The target (one brand's context windows) is compared with all other brands'
    windows; the prior is the background word distribution scaled to `prior` tokens.
    """
    total = sum(background_counts.values())
    n_i = sum(target_counts.values())
    n_j = total - n_i
    results = []
    for word, y_i in target_counts.items():
        if y_i < minimum:
            continue
        y_j = background_counts[word] - y_i
        a = prior*background_counts[word]/total
        delta = (math.log((y_i+a)/(n_i+prior-y_i-a)) - math.log((y_j+a)/(n_j+prior-y_j-a)))
        results.append((delta/math.sqrt(1/(y_i+a) + 1/(y_j+a)), word))
    return [w for _, w in sorted(results, reverse=True)[:top]]


STOP = set(ENGLISH_STOP_WORDS) | {'said', 'says', 'also', 'new', 'year', 'years', 'will', 'including', 'travel', 'tourism', 'hotel',
                                  'hotels', 'company', 'companies', 'group', 'brand', 'brands', 'percent', 'million', 'billion',
                                  'according', 'one', 'two', 'first', 'like', 'just', 'well', 'many', 'much', 'more', 'most', 've',
                                  "it's", "'s", 'its', 'per', 'cent', 'mr', 'ms'}


def tokens(text, exclude):
    """Lower-case content words only: capitalised words are mostly people, places and other names."""
    return [w for w in WORD.findall(text) if w.islower() and w not in STOP and w not in exclude and len(w) > 2]


# ---------------------------------------------------------------- figures

INK, INK2, MUTED, GRID, AXIS, SURFACE = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7', '#fcfcfb'
SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
BLUES = ['#f4f8fd', '#cde2fb', '#b7d3f6', '#9ec5f4', '#86b6ef', '#6da7ec', '#5598e7', '#3987e5', '#2a78d6', '#256abf',
         '#1c5cab', '#184f95', '#104281', '#0d366b']
NEGATIVE, NEUTRAL, POSITIVE = '#e34948', '#d9d8d2', '#2a78d6'


def style():
    plt.rcParams.update({'font.family': ['Segoe UI', 'DejaVu Sans'], 'font.size': 9, 'axes.edgecolor': AXIS,
                         'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2, 'text.color': INK,
                         'axes.titlesize': 11, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left',
                         'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE, 'savefig.facecolor': SURFACE,
                         'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': False,
                         'grid.color': GRID, 'grid.linewidth': .8, 'legend.frameon': False})


def titles(ax, title, subtitle, gap=0):
    """Title and subtitle anchored to the plot's top-left corner, above any legend."""
    ax.annotate(subtitle, xy=(0, 1), xycoords='axes fraction', xytext=(0, 8+gap), textcoords='offset points',
                fontsize=8.5, color=INK2, ha='left', va='bottom')
    ax.annotate(title, xy=(0, 1), xycoords='axes fraction', xytext=(0, 23+gap), textcoords='offset points',
                fontsize=11, fontweight='bold', color=INK, ha='left', va='bottom')


def save(fig, name, note=None):
    if note:
        fig.text(.01, .008, note, fontsize=7.5, color=MUTED, ha='left', va='bottom')
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES/name, dpi=200, bbox_inches='tight', pad_inches=.15)
    plt.close(fig)


def heatmap(matrix, name, title, subtitle, fmt='{:.0f}', note=None, mark=None, cmap_max=None, figsize=None):
    from matplotlib.colors import LinearSegmentedColormap
    if matrix.empty or matrix.isna().all().all():
        return
    values = matrix.to_numpy(dtype=float)
    cmap = LinearSegmentedColormap.from_list('blues', BLUES).with_extremes(bad='#efeee9')
    vmax = cmap_max or np.nanmax(values)
    fig, ax = plt.subplots(figsize=figsize or (max(7, .62*matrix.shape[1]+2.6), max(3, .36*matrix.shape[0]+1.4)))
    ax.imshow(np.ma.masked_invalid(values), aspect='auto', cmap=cmap, vmin=0, vmax=vmax)
    ax.set_xticks(range(matrix.shape[1]), [str(c) for c in matrix.columns], rotation=0 if matrix.shape[1] < 13 and max(len(str(c)) for c in matrix.columns) < 6 else 35,
                  ha='center' if matrix.shape[1] < 13 and max(len(str(c)) for c in matrix.columns) < 6 else 'right')
    ax.set_yticks(range(matrix.shape[0]), matrix.index)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v = values[i, j]
            if np.isnan(v):
                continue
            bold = mark is not None and bool(mark.iloc[i, j])
            ax.text(j, i, fmt.format(v), ha='center', va='center', fontsize=7.5, fontweight='bold' if bold else 'normal',
                    color='white' if v > .55*vmax else INK)
            if bold:
                ax.add_patch(plt.Rectangle((j-.5, i-.5), 1, 1, fill=False, edgecolor=INK, linewidth=1.2))
    titles(ax, title, subtitle)
    save(fig, name, note)


def hbar(labels, values, name, title, subtitle, fmt='{:.0f}%', color=SERIES[0], xlabel=None):
    if not len(values) or not np.isfinite(values).any():
        return
    fig, ax = plt.subplots(figsize=(7.2, .34*len(labels)+1.2))
    y = np.arange(len(labels))[::-1]
    ax.barh(y, values, height=.56, color=color)
    for yi, v in zip(y, values):
        ax.text(v + max(values)*.01, yi, fmt.format(v), va='center', fontsize=8, color=INK2)
    ax.set_yticks(y, labels)
    ax.tick_params(axis='y', length=0)
    ax.spines['left'].set_visible(False)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(values)*1.12)
    if xlabel:
        ax.set_xlabel(xlabel)
    titles(ax, title, subtitle)
    save(fig, name)


def sentiment_bars(frame, name, title, subtitle):
    """Negative | neutral | positive shares, one row per item (diverging encoding)."""
    frame = frame.dropna(subset=['negative_pct', 'neutral_pct', 'positive_pct'])
    if frame.empty:
        return
    fig, ax = plt.subplots(figsize=(7.2, .34*len(frame)+1.4))
    y = np.arange(len(frame))[::-1]
    left = np.zeros(len(frame))
    for column, color, text in [('negative_pct', NEGATIVE, 'Negative'), ('neutral_pct', NEUTRAL, 'Neutral'), ('positive_pct', POSITIVE, 'Positive')]:
        values = frame[column].to_numpy()
        ax.barh(y, values, left=left, height=.56, color=color, edgecolor=SURFACE, linewidth=1.5, label=text)
        for yi, l, v in zip(y, left, values):
            if v >= 7:
                ax.text(l+v/2, yi, f'{v:.0f}', ha='center', va='center', fontsize=7.5, color='white' if color != NEUTRAL else INK)
        left += values
    ax.set_yticks(y, frame['item'])
    ax.tick_params(axis='y', length=0)
    ax.set_xlim(0, 100)
    ax.set_xlabel('% of articles (tone of sentences about the item, RoBERTa sentiment model)')
    for spine in ('left',):
        ax.spines[spine].set_visible(False)
    ax.legend(ncol=3, loc='lower left', bbox_to_anchor=(0, 1.0), fontsize=8, handlelength=1, borderaxespad=0.3)
    titles(ax, title, subtitle, gap=18)
    save(fig, name)


def trend_lines(pooled, themes, name, title, subtitle):
    if pooled.empty:
        return
    fig, ax = plt.subplots(figsize=(7.4, 3.9))
    years = sorted(pooled.year.unique())
    for color, theme in zip(SERIES, themes):
        series = pooled[pooled.theme == theme].set_index('year').reindex(years).share_pct
        ax.plot(years, series, color=color, linewidth=2, solid_capstyle='round', label=theme)
        ax.scatter([years[-1]], [series.iloc[-1]], s=22, color=color, edgecolor=SURFACE, linewidth=1.5, zorder=3)
    ax.set_xticks(years, [f'{y}*' if y in (2016, 2026) else str(y) for y in years])
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_ylabel('% of articles discussing the theme')
    ax.set_ylim(0, None)
    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=8)
    titles(ax, title, subtitle)
    save(fig, name, '* 2016 covers 10 Oct-31 Dec only; 2026 covers 1 Jan-10 Oct. Equal weight per website.')


# ---------------------------------------------------------------- main analysis

def main():
    style()
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    db = connect()
    docs = pd.read_sql_query('SELECT * FROM documents', db)
    urls = pd.read_sql_query('SELECT url, source, status, discovered_via, archive_snapshot FROM urls', db)
    db.close()
    if docs.empty:
        raise ValueError('No documents collected; run collection first.')
    docs['year'] = pd.to_datetime(docs.published_at, errors='coerce').dt.year.astype('Int64')
    docs = docs.merge(urls[['url', 'discovered_via']], on='url', how='left')
    docs['route'] = np.select([docs.discovered_via.fillna('').str.startswith('wayback'), docs.discovered_via.fillna('').str.startswith('id_sample')],
                              ['web archive (Wayback Machine)', 'live site, random ID sample'], 'live site')
    eligible = de_duplicate(docs[docs.eligible == 1])
    core = (eligible[eligible.content_type.isin(CORE_TYPES)].sort_values('published_at')
            .drop_duplicates(['source', 'year', 'story_id']).reset_index(drop=True))
    if core.empty:
        raise ValueError('No eligible English articles with usable dates.')
    core['year'] = core.year.astype(int)
    core['current'] = core.published_at >= CURRENT_START
    event('analysis_started', documents=len(docs), eligible=len(eligible), core=len(core))

    theme_rows, brand_rows, org_rows, windows = [], [], [], []
    for i, row in enumerate(core.itertuples()):
        t, b, o, w = code_article(row)
        theme_rows += t
        brand_rows += b
        org_rows += o
        windows += w
        if (i+1) % 1000 == 0:
            event('analysis_progress', coded=i+1, of=len(core))
    score_rows(theme_rows + brand_rows)
    themes = pd.DataFrame(theme_rows, columns=['doc_id', 'theme', 'mentions', 'distinct_terms', 'in_title', 'lead_mentions', 'discussed',
                                               'sentiment', 'sentiment_label', 'sentences', 'matched_terms'])
    brands = pd.DataFrame(brand_rows, columns=['doc_id', 'brand', 'group', 'mentions', 'in_title', 'sentiment', 'sentiment_label', 'themes_nearby'])
    orgs = pd.DataFrame(org_rows, columns=['doc_id', 'organization', 'mentions'])
    meta = core[['doc_id', 'source', 'year', 'current', 'published_at']]
    themes = themes.merge(meta, on='doc_id')
    brands = brands.merge(meta, on='doc_id')
    orgs = orgs.merge(meta, on='doc_id')
    discussed = themes[themes.discussed]

    # Corpus description -------------------------------------------------
    csv(docs.drop(columns=['body', 'raw_path', 'discovered_via']).assign(in_analysis=docs.doc_id.isin(core.doc_id)), 'document_inventory.csv')
    coverage = core.groupby(['source', 'year']).size().unstack(fill_value=0).reindex(index=list(SOURCES), columns=range(2016, 2027), fill_value=0)
    csv(coverage.reset_index().rename(columns={'source': 'website'}).assign(website=lambda d: d.website.map(SHORT)), 'coverage_by_website_year.csv')
    sources = []
    for s, c in SOURCES.items():
        d, k = docs[docs.source == s], core[core.source == s]
        sources.append({'website': c['name'], 'source_id': s, 'type': SOURCE_TYPE[c['group']], 'url': c['base'],
                        'documents_collected': len(d), 'eligible_documents': int((eligible.source == s).sum()),
                        'articles_analysed': len(k), 'current_window_articles': int(k.current.sum()),
                        'first_article': k.published_at.min() if len(k) else '', 'last_article': k.published_at.max() if len(k) else '',
                        'years_with_20plus_articles': int((k.groupby('year').size() >= MIN_CELL).sum()) if len(k) else 0,
                        'from_web_archive_pct': round(100*(k.route == 'web archive (Wayback Machine)').mean(), 1) if len(k) else 0,
                        'collection_routes': '; '.join(f'{r} ({n})' for r, n in k.route.value_counts().items())})
    sources = csv(pd.DataFrame(sources), 'sources.csv')
    csv(docs.assign(exclusion_reason=docs.exclusion_reason.replace('', 'included')).groupby(['source', 'exclusion_reason']).size()
        .rename('documents').reset_index(), 'exclusions.csv')

    # Question 1: current top themes and sentiment ------------------------
    current = core[core.current]
    cur_n = current.groupby('source').size()
    cur_sources = cur_n[cur_n >= MIN_CELL].index
    cur_disc = discussed[discussed.current]
    rows = []
    for theme in THEMES:
        sub = cur_disc[cur_disc.theme == theme]
        per_source = [100*(sub.source == s).sum()/cur_n[s] for s in (cur_sources if len(cur_sources) else cur_n.index)]
        mentioned = themes[(themes.current) & (themes.theme == theme)]
        rows.append(dict(theme=theme, share_pct=np.mean(per_source) if per_source else np.nan,
                         article_weighted_pct=100*len(sub)/max(len(current), 1), articles=len(sub),
                         mentioned_pct=100*len(mentioned)/max(len(current), 1), websites_discussing=sub.source.nunique(),
                         positive_pct=100*(sub.sentiment_label == 'positive').mean() if len(sub) else np.nan,
                         neutral_pct=100*(sub.sentiment_label == 'neutral').mean() if len(sub) else np.nan,
                         negative_pct=100*(sub.sentiment_label == 'negative').mean() if len(sub) else np.nan,
                         mean_sentiment=sub.sentiment.mean()))
    ranking = pd.DataFrame(rows).sort_values('share_pct', ascending=False).reset_index(drop=True)
    ranking.insert(0, 'rank', range(1, len(ranking)+1))
    ranking['net_sentiment'] = ranking.positive_pct - ranking.negative_pct
    csv(ranking.round(2), 'q1_current_theme_ranking.csv')
    by_site = (cur_disc.groupby(['theme', 'source']).size().unstack(fill_value=0).reindex(index=ranking.theme, columns=list(cur_n.index), fill_value=0)
               .div(cur_n, axis=1).mul(100).round(1))
    csv(by_site.rename(columns=SHORT).reset_index(), 'q1_current_theme_share_by_website.csv')
    # Sentiment over the whole period, and by year for every theme.
    sent_all = discussed.groupby('theme').agg(articles=('doc_id', 'size'), mean_sentiment=('sentiment', 'mean'),
                                              positive_pct=('sentiment_label', lambda x: 100*(x == 'positive').mean()),
                                              negative_pct=('sentiment_label', lambda x: 100*(x == 'negative').mean())).reset_index()
    sent_all['net_sentiment'] = sent_all.positive_pct - sent_all.negative_pct
    csv(sent_all.sort_values('net_sentiment').round(2), 'q1_theme_sentiment_all_years.csv')
    sent_year = discussed.groupby(['theme', 'year']).agg(articles=('doc_id', 'size'), mean_sentiment=('sentiment', 'mean'),
                                                         positive_pct=('sentiment_label', lambda x: 100*(x == 'positive').mean()),
                                                         negative_pct=('sentiment_label', lambda x: 100*(x == 'negative').mean())).reset_index()
    sent_year['net_sentiment'] = sent_year.positive_pct - sent_year.negative_pct
    csv(sent_year.round(2), 'q1_theme_sentiment_by_year.csv')

    top10 = ranking.head(10)
    hbar(list(top10.theme), list(top10.share_pct), 'q1_top10_current_themes.png',
         'Ten leading themes, 11 Oct 2025 - 10 Oct 2026',
         f'% of articles that discuss each theme (mean of {len(cur_sources)} websites, equal weight; {len(current):,} articles)')
    sentiment_bars(top10.assign(item=top10.theme), 'q1_top10_sentiment.png', 'Tone of the ten leading themes',
                   'Share of articles discussing the theme whose theme sentences are positive, neutral or negative')

    # Question 2: themes over time --------------------------------------
    cells = theme_cells(core, discussed)
    csv(cells.round(2).assign(website=lambda d: d.source.map(SHORT)), 'q2_theme_share_by_website_year.csv')
    pooled = equal_source(cells, ['year'])
    csv(pooled.round(2), 'q2_theme_share_by_year.csv')
    top_year = (pooled.sort_values(['year', 'share_pct'], ascending=[True, False]).groupby('year').head(5)
                .assign(rank=lambda d: d.groupby('year').cumcount()+1))
    wide = top_year.pivot(index='year', columns='rank', values='theme')
    wide.columns = [f'#{c}' for c in wide.columns]
    shares = top_year.pivot(index='year', columns='rank', values='share_pct').round(1)
    shares.columns = [f'#{c} share %' for c in shares.columns]
    year_sources = (cells[cells.in_yearly_comparison].drop_duplicates(['source', 'year']).groupby('year')
                    .agg(websites=('source', 'nunique'), articles=('articles', 'sum')).reset_index())
    top_table = wide.join(shares).reset_index().merge(year_sources, on='year')
    csv(top_table, 'q2_top_themes_each_year.csv')
    matrix = pooled.pivot(index='theme', columns='year', values='share_pct')
    order = matrix.mean(axis=1).sort_values(ascending=False).index
    matrix = matrix.loc[order]
    ranks = matrix.rank(ascending=False, method='first') <= 3
    heatmap(matrix, 'q2_themes_by_year_heatmap.png', 'Theme prominence by year, 2016-2026',
            '% of articles discussing each theme (equal weight per website). Outlined: the year\'s top three.',
            note='2016 = 10 Oct-31 Dec; 2026 = 1 Jan-10 Oct. Websites enter a year when they have 20+ articles in it.', mark=ranks)
    movers = ['Artificial intelligence', 'Sustainability & climate', 'COVID-19 pandemic', 'Workforce, skills & education',
              'Social media & digital marketing']
    trend_lines(pooled, movers, 'q2_selected_theme_trends.png', 'How selected themes rose and fell',
                '% of articles discussing the theme each year')
    early, late = pooled[pooled.year.between(2017, 2019)], pooled[pooled.year.between(2023, 2025)]
    change = (early.groupby('theme').share_pct.mean().rename('share_2017_2019').to_frame()
              .join(late.groupby('theme').share_pct.mean().rename('share_2023_2025')))
    change['change_pp'] = change.share_2023_2025 - change.share_2017_2019
    csv(change.sort_values('change_pp', ascending=False).reset_index().round(2), 'q2_change_2017_19_vs_2023_25.csv')
    # Robustness: websites that are present in every year 2017-2025.
    panel = [s for s in SOURCES if all(((cells.source == s) & (cells.year == y) & cells.in_yearly_comparison).any() for y in range(2017, 2026))]
    panel_pooled = equal_source(cells[cells.source.isin(panel)], ['year']).assign(panel='; '.join(SHORT[s] for s in panel))
    csv(panel_pooled.round(2), 'q2_theme_share_by_year_fixed_panel.csv')

    # Question 3: each website's focus -----------------------------------
    site = (discussed.groupby(['source', 'theme']).size().unstack(fill_value=0).reindex(columns=list(THEMES), fill_value=0)
            .div(core.groupby('source').size(), axis=0).mul(100))
    site = site.loc[[s for s in SOURCES if s in site.index]]
    distinct = site.copy()
    for s in site.index:
        others = site.drop(index=s).mean()
        distinct.loc[s] = site.loc[s] / others.replace(0, np.nan)
    profile = []
    for s in site.index:
        top = site.loc[s].sort_values(ascending=False).head(5)
        dist = distinct.loc[s][site.loc[s] >= 10].sort_values(ascending=False).head(3)
        profile.append({'website': SHORT[s], 'articles': int((core.source == s).sum()),
                        'years': f"{core[core.source == s].year.min()}-{core[core.source == s].year.max()}",
                        **{f'top_{i+1}': f'{t} ({v:.0f}%)' for i, (t, v) in enumerate(top.items())},
                        'most_distinctive': '; '.join(f'{t} ({v:.1f}x)' for t, v in dist.items())})
    csv(pd.DataFrame(profile), 'q3_website_profiles.csv')
    csv(site.round(1).rename(index=SHORT).reset_index().rename(columns={'source': 'website'}), 'q3_theme_share_by_website.csv')
    csv(distinct.round(2).rename(index=SHORT).reset_index().rename(columns={'source': 'website'}), 'q3_theme_distinctiveness_by_website.csv')
    site_matrix = site.T.loc[order].rename(columns=SHORT)
    heatmap(site_matrix, 'q3_themes_by_website_heatmap.png', 'What each website talks about',
            '% of each website\'s articles (2016-2026) that discuss the theme. Outlined: the site\'s top three.',
            mark=site_matrix.rank(ascending=False, method='first') <= 3, figsize=(8.2, 7.4))

    # Question 4: brands and their associations ----------------------------
    n_total, n_year = len(core), core.groupby('year').size()
    brand_rank = (brands.groupby(['brand', 'group']).agg(articles=('doc_id', 'nunique'), mentions=('mentions', 'sum'),
                                                       websites=('source', 'nunique'), current_articles=('current', 'sum'),
                                                       title_articles=('in_title', 'sum'), mean_sentiment=('sentiment', 'mean'))
                  .reset_index().sort_values('articles', ascending=False))
    brand_rank['per_1000_articles'] = 1000*brand_rank.articles/n_total
    csv(brand_rank.round(3), 'q4_brand_ranking.csv')
    group_articles = brands.drop_duplicates(['doc_id', 'group'])
    groups = (group_articles.groupby('group').agg(articles=('doc_id', 'size'), websites=('source', 'nunique'), current_articles=('current', 'sum'))
              .reset_index())
    portfolio = brands.groupby(['group', 'brand']).doc_id.nunique().reset_index().sort_values('doc_id', ascending=False)
    groups['brands_mentioned'] = groups.group.map(lambda g: '; '.join(f'{b} ({n})' for b, n in portfolio[portfolio.group == g][['brand', 'doc_id']].head(6).values))
    groups['gbm_2026_rank'] = groups.group.map(GBM_RANK)
    groups['per_1000_articles'] = 1000*groups.articles/n_total
    groups = groups.sort_values('articles', ascending=False)
    # Sentiment around each brand group's mentions.
    gs = brands.groupby('group').agg(mean_sentiment=('sentiment', 'mean'), positive_pct=('sentiment_label', lambda x: 100*(x == 'positive').mean()),
                                     neutral_pct=('sentiment_label', lambda x: 100*(x == 'neutral').mean()),
                                     negative_pct=('sentiment_label', lambda x: 100*(x == 'negative').mean())).reset_index()
    groups = groups.merge(gs, on='group', how='left')
    groups['net_sentiment'] = groups.positive_pct - groups.negative_pct
    by_source = group_articles.groupby(['group', 'source']).size().unstack(fill_value=0)
    groups['main_websites'] = groups.group.map(lambda g: '; '.join(f'{SHORT[s]} ({n})' for s, n in by_source.loc[g].sort_values(ascending=False).head(3).items() if n))
    # Associations: themes in the brand's context windows (mention sentence +/- 1).
    window_frame = pd.DataFrame(windows, columns=['doc_id', 'brand', 'group', 'text'])
    group_windows = window_frame.groupby(['doc_id', 'group']).text.apply(' '.join).reset_index()
    window_theme = group_windows.assign(themes=group_windows.text.map(lambda t: list(theme_hits(t))))
    exploded = window_theme.explode('themes').dropna(subset=['themes'])
    baseline = exploded.drop_duplicates(['doc_id', 'group', 'themes']).groupby('themes').size()/len(group_windows)
    assoc = exploded.drop_duplicates(['doc_id', 'group', 'themes']).groupby(['group', 'themes']).size().rename('articles').reset_index()
    assoc = assoc.merge(group_windows.groupby('group').size().rename('group_articles').reset_index(), on='group')
    assoc['share_pct'] = 100*assoc.articles/assoc.group_articles
    assoc['lift'] = assoc.share_pct/100/assoc.themes.map(baseline)
    assoc = assoc.rename(columns={'themes': 'theme'})
    csv(assoc.sort_values(['group', 'articles'], ascending=[True, False]).round(3), 'q4_brand_theme_associations.csv')
    strong = assoc[(assoc.group_articles >= MIN_BRAND) & (assoc.articles >= 5)]
    groups['top_associated_themes'] = groups.group.map(lambda g: '; '.join(
        f'{r.theme} ({r.share_pct:.0f}%, {r.lift:.1f}x)' for r in strong[strong.group == g].sort_values('share_pct', ascending=False).head(3).itertuples()))
    groups['most_distinctive_theme'] = groups.group.map(lambda g: '; '.join(
        f'{r.theme} ({r.lift:.1f}x)' for r in strong[(strong.group == g) & (strong.share_pct >= 10)].sort_values('lift', ascending=False).head(2).itertuples()))
    # Distinctive vocabulary around each brand group.
    background = Counter()
    group_tokens = {}
    name_words = {w for name in list(BRANDS)+list(GBM_TOP10) for w in TOKEN.findall(name.lower())}
    for g, frame in group_windows.groupby('group'):
        counts = Counter(t for text in frame.text for t in tokens(text, name_words))
        group_tokens[g] = counts
        background.update(counts)
    groups['associated_words'] = groups.group.map(lambda g: ', '.join(log_odds_terms(group_tokens.get(g, Counter()), background, top=10))
                                                  if groups.set_index('group').articles.get(g, 0) >= MIN_BRAND else '')
    csv(groups.round(2), 'q4_brand_groups.csv')
    gbm = groups[groups.group.isin(GBM_TOP10)].sort_values('gbm_2026_rank')
    csv(gbm.round(2), 'q4_gbm_top10_brands.csv')
    # Over time (per 1,000 articles, so growth in the corpus is not mistaken for growth in attention).
    trend = (group_articles[group_articles.group.isin(GBM_TOP10)].groupby(['group', 'year']).size().unstack(fill_value=0)
             .reindex(index=GBM_TOP10, columns=range(2016, 2027), fill_value=0).div(n_year, axis=1).mul(1000))
    csv(trend.round(2).reset_index(), 'q4_gbm_brands_per_1000_articles_by_year.csv')
    # Co-mentions between brand groups in the same article.
    pairs = Counter()
    for _, frame in group_articles.groupby('doc_id'):
        names = sorted(set(frame.group))
        for i, a in enumerate(names):
            for b in names[i+1:]:
                pairs[(a, b)] += 1
    group_n = group_articles.groupby('group').size()
    co = pd.DataFrame([dict(brand_a=a, brand_b=b, articles=n, jaccard=n/(group_n[a]+group_n[b]-n)) for (a, b), n in pairs.items()])
    if not co.empty:
        co = co.sort_values('articles', ascending=False)
    csv(co.round(3), 'q4_brand_co_mentions.csv')
    # How much each website talks about companies at all.
    any_brand = brands.drop_duplicates('doc_id').groupby('source').size()
    gbm_brand = brands[brands.group.isin(GBM_TOP10)].drop_duplicates('doc_id').groupby('source').size()
    per_site = core.groupby('source').size()
    csv(pd.DataFrame({'website': [SHORT[s] for s in per_site.index], 'articles': per_site.values,
                      'pct_mentioning_any_brand': (100*any_brand.reindex(per_site.index, fill_value=0)/per_site).round(1).values,
                      'pct_mentioning_gbm_top10': (100*gbm_brand.reindex(per_site.index, fill_value=0)/per_site).round(1).values}),
        'q4_brand_mentions_by_website.csv')
    # Organisations other than the publisher itself.
    org_rank = orgs.groupby('organization').agg(articles=('doc_id', 'nunique'), websites=('source', 'nunique')).reset_index().sort_values('articles', ascending=False)
    if not orgs.empty:
        org_site = orgs.drop_duplicates(['doc_id', 'organization']).groupby(['organization', 'source']).size().unstack(fill_value=0).rename(columns=SHORT)
        org_rank = org_rank.merge(org_site.reset_index(), on='organization')
    csv(org_rank, 'q4_organisation_mentions.csv')

    hbar(list(gbm.group), list(gbm.articles), 'q4_gbm_brand_mentions.png', 'Global Brands Magazine top 10: how often each is discussed',
         'Articles (2016-2026) mentioning the company or any of its brands; ordered by the magazine\'s 2026 rank', fmt='{:.0f}')
    heatmap(trend.round(1), 'q4_gbm_brands_by_year.png', 'Brand attention over time',
            'Articles mentioning the brand family per 1,000 articles analysed that year', fmt='{:.0f}',
            note='Includes sub-brands (e.g. Ritz-Carlton -> Marriott International) under 2026 ownership.')
    top_groups = groups[groups.articles >= MIN_BRAND].head(15).group
    am = (assoc[assoc.group.isin(top_groups)].pivot(index='group', columns='theme', values='share_pct').reindex(index=top_groups)
          .reindex(columns=[t for t in order if t in assoc.theme.unique()]).fillna(0))
    heatmap(am.T, 'q4_brand_theme_heatmap.png', 'Brand associations: themes discussed around each brand',
            '% of the brand\'s articles in which the theme appears within one sentence of the brand. Outlined: the brand\'s top three.',
            mark=am.T.rank(ascending=False, method='first') <= 3, figsize=(9.6, 7.4))
    sb = groups[groups.articles >= 40].sort_values('net_sentiment', ascending=False).head(15)
    sentiment_bars(sb.assign(item=sb.group), 'q4_brand_sentiment.png', 'Tone of sentences mentioning each brand',
                   'Brand families with 40+ articles; sorted by positive minus negative share')

    # Data-driven check: unsupervised topics (TF-IDF + NMF) ------------------
    topics, topic_years, dominant = topic_model(core)
    if len(dominant):
        # Which dictionary theme do most articles of each data-driven topic discuss?
        members = dominant.rename_axis('doc_id').reset_index()
        hits = members.merge(discussed[['doc_id', 'theme']], on='doc_id').groupby(['topic', 'theme']).size().rename('n').reset_index()
        hits = hits.merge(members.groupby('topic').size().rename('articles_in_topic').reset_index(), on='topic')
        hits['share_pct'] = 100*hits.n/hits.articles_in_topic
        best = hits.sort_values('share_pct', ascending=False).drop_duplicates('topic').set_index('topic')
        topics['closest_theme'] = topics.topic.map(best.theme)
        topics['closest_theme_share_pct'] = topics.topic.map(best.share_pct).round(1)
    csv(topics, 'nmf_topics.csv')
    csv(topic_years, 'nmf_topic_share_by_year.csv')

    # Article-level coding, without text --------------------------------
    csv(themes.drop(columns=['current']), 'article_themes.csv')
    csv(brands.drop(columns=['current']), 'article_brands.csv')
    csv(core.drop(columns=['body', 'raw_path', 'discovered_via']), 'articles_analysed.csv')

    figures_coverage(coverage)
    workbook(dict(sources=sources, coverage=coverage, ranking=ranking, by_site=by_site, sent_all=sent_all, top_table=top_table,
                  pooled=pooled, change=change, panel=panel_pooled, profile=pd.DataFrame(profile), site=site, distinct=distinct,
                  groups=groups, gbm=gbm, assoc=assoc, trend=trend, co=co, org=org_rank, brand_rank=brand_rank, topics=topics))
    (OUTPUT/'codebook.json').write_text(json.dumps(dict(version=CODEBOOK_VERSION, themes=THEMES,
        brands={k: dict(group=v[0], pattern=v[1]) for k, v in BRANDS.items()}, organizations=ORGANIZATIONS,
        discussed_rule=f'term in headline, OR 2+ mentions in the first {LEAD_WORDS} words, OR 3+ mentions using 2+ distinct terms',
        sentiment=f'{sentiment.MODEL} (revision {sentiment.REVISION}); class probabilities averaged over up to {MAX_SENTENCES} sentences mentioning the discussed theme or brand; label = most probable class; score = P(positive) - P(negative)'),
        indent=2, ensure_ascii=False), 'utf-8')
    # Agreement of the automated coding with the independent validation reading.
    from .validation import score as validation_score
    v_summary, v_theme = validation_score(themes, core.doc_id)
    if v_summary is not None:
        csv(v_summary, 'validation_summary.csv')
        csv(v_theme.round(3), 'validation_by_theme.csv')
    checks = quality_checks(core, themes, brands, cells, coverage, ranking)
    summary = dict(created_at=now(), window_start=START, window_end=END, current_window_start=CURRENT_START,
                   documents_collected=len(docs), eligible_documents=len(eligible), articles_analysed=len(core),
                   unique_stories=int(core.story_id.nunique()), current_articles=len(current),
                   websites_with_articles=sorted(SHORT[s] for s in core.source.unique()), codebook_version=CODEBOOK_VERSION,
                   theme_mentions=len(themes), theme_discussions=int(themes.discussed.sum()), brand_mentions=len(brands),
                   checks_passed=all(c['passed'] for c in checks), python=platform.python_version())
    atomic_json(OUTPUT/'run_summary.json', summary)
    atomic_json(OUTPUT/'QUALITY_CHECKS.json', dict(created_at=summary['created_at'], checks=checks))
    event('analysis_finished', **{k: v for k, v in summary.items() if k in ('articles_analysed', 'current_articles', 'checks_passed')})
    return summary


def topic_model(core, k=20):
    if len(core) < 10*k:
        return (pd.DataFrame(columns=['topic', 'top_terms', 'articles', 'main_websites', 'peak_year']),
                pd.DataFrame(columns=['year', 'topic', 'share_pct']), pd.Series(dtype=int))
    stop = sorted(set(ENGLISH_STOP_WORDS) | STOP | {'unwto', 'wttc', 'pata', 'ahla', 'cto', 'etc', 'un', 'www', 'http', 'https', 'org', 'com',
                                                    'travel', 'tourism', 'industry', 'sector', 'world', 'council', 'organization',
                                                    'association', 'caribbean', 'european', 'commission', 'pacific', 'asia', 'lodging',
                                                    'american', 'secretary', 'general', 'president', 'ceo', 'chief', 'executive'})
    vectorizer = TfidfVectorizer(stop_words=stop, min_df=5, max_df=.5, max_features=30000, ngram_range=(1, 2), sublinear_tf=True,
                                 token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z-]+[a-zA-Z]\b')
    x = vectorizer.fit_transform(core.title.fillna('') + '. ' + core.body.fillna(''))
    # Train on at most 120 articles per website-year so large sources do not define the topics.
    sample = core.sample(frac=1, random_state=42).groupby(['source', 'year']).head(120).index
    model = NMF(n_components=k, init='nndsvda', random_state=42, max_iter=600).fit(x[core.index.get_indexer(sample)])
    weights = model.transform(x)
    words = np.array(vectorizer.get_feature_names_out())
    dominant = weights.argmax(axis=1)
    rows = []
    for i, component in enumerate(model.components_):
        members = core[dominant == i]
        rows.append(dict(topic=i+1, top_terms=', '.join(words[np.argsort(component)[-12:][::-1]]), articles=int((dominant == i).sum()),
                         main_websites='; '.join(f'{SHORT[s]} ({n})' for s, n in members.source.value_counts().head(3).items()),
                         peak_year=int(members.year.value_counts().idxmax()) if len(members) else None))
    years = (pd.DataFrame({'year': core.year, 'topic': dominant+1}).groupby(['year', 'topic']).size()
             .div(core.groupby('year').size(), level='year').mul(100).rename('share_pct').reset_index())
    return pd.DataFrame(rows), years.round(2), pd.Series(dominant+1, index=core.doc_id, name='topic')


def figures_coverage(coverage):
    matrix = coverage.rename(index=SHORT).replace(0, np.nan)
    heatmap(matrix, 'coverage_by_website_year.png', 'Articles analysed, by website and year',
            'English news, press releases and blog posts after cleaning and de-duplication',
            note='Blank = no articles collected. 2016 = 10 Oct-31 Dec; 2026 = 1 Jan-10 Oct.')


def quality_checks(core, themes, brands, cells, coverage, ranking):
    checks = []

    def check(name, passed, detail=''):
        checks.append(dict(check=name, passed=bool(passed), detail=detail))
    check('articles inside study window', core.published_at.between(START, END).all())
    check('one occurrence per story per website-year', not core.duplicated(['source', 'year', 'story_id']).any())
    check('every coded row refers to an analysed article', themes.doc_id.isin(core.doc_id).all() and brands.doc_id.isin(core.doc_id).all())
    check('one theme row per article and theme', not themes.duplicated(['doc_id', 'theme']).any())
    check('coverage table equals article count', int(coverage.to_numpy().sum()) == len(core), f'{int(coverage.to_numpy().sum())} vs {len(core)}')
    check('cell shares within 0-100', cells.share_pct.between(0, 100).all())
    check('sentiment scores within -1..1', themes.sentiment.dropna().between(-1, 1).all() and brands.sentiment.dropna().between(-1, 1).all())
    check('every discussed theme has a sentiment score', themes[themes.discussed].sentiment.notna().all())
    check('current ranking covers every theme once', sorted(ranking.theme) == sorted(THEMES))
    return checks


def workbook(t):
    """One Excel file with every result table, for readers who do not use CSV."""
    path = OUTPUT/'RESULTS.xlsx'
    readme = pd.DataFrame({'Sheet': ['1 Sources', '2 Coverage', '3 Q1 Top themes now', '4 Q1 Themes by site now', '5 Q1 Theme sentiment',
                                     '6 Q2 Top themes per year', '7 Q2 Theme share by year', '8 Q2 Change', '9 Q2 Fixed panel',
                                     '10 Q3 Website profiles', '11 Q3 Theme by website', '12 Q3 Distinctiveness', '13 Q4 GBM top 10',
                                     '14 Q4 Brand families', '15 Q4 Brand-theme', '16 Q4 Brands by year', '17 Q4 Co-mentions',
                                     '18 Q4 Organisations', '19 Q4 Individual brands', '20 Data-driven topics'],
                           'Contents': ['The nine websites, what was collected and how', 'Articles analysed per website and year',
                                        'Theme ranking for 11 Oct 2025-10 Oct 2026 with sentiment', 'Same, per website',
                                        'Sentiment per theme across 2016-2026', 'The five leading themes in each year',
                                        'Equal-website share of articles discussing each theme, by year',
                                        'Average share 2017-2019 vs 2023-2025', 'Yearly shares using only websites present every year',
                                        'Leading and most distinctive themes per website', '% of each site\'s articles discussing each theme',
                                        'Site share divided by the other sites\' average (1.0 = typical)',
                                        'The ten companies listed by Global Brands Magazine (2026)', 'All brand families mentioned',
                                        'Themes appearing near each brand family', 'Mentions per 1,000 articles each year',
                                        'Brand families named in the same article', 'Other industry bodies mentioned (self-mentions excluded)',
                                        'Each brand name separately', 'Unsupervised TF-IDF/NMF topics used as a cross-check']})
    sheets = [('README', readme), ('1 Sources', t['sources']), ('2 Coverage', t['coverage'].rename(index=SHORT).reset_index()),
              ('3 Q1 Top themes now', t['ranking']), ('4 Q1 Themes by site now', t['by_site'].rename(columns=SHORT).reset_index()),
              ('5 Q1 Theme sentiment', t['sent_all']), ('6 Q2 Top themes per year', t['top_table']),
              ('7 Q2 Theme share by year', t['pooled'].pivot(index='theme', columns='year', values='share_pct').reset_index()),
              ('8 Q2 Change', t['change'].reset_index()), ('9 Q2 Fixed panel', t['panel'].pivot(index='theme', columns='year', values='share_pct').reset_index()),
              ('10 Q3 Website profiles', t['profile']), ('11 Q3 Theme by website', t['site'].rename(index=SHORT).T.reset_index()),
              ('12 Q3 Distinctiveness', t['distinct'].rename(index=SHORT).T.reset_index()), ('13 Q4 GBM top 10', t['gbm']),
              ('14 Q4 Brand families', t['groups']), ('15 Q4 Brand-theme', t['assoc']), ('16 Q4 Brands by year', t['trend'].reset_index()),
              ('17 Q4 Co-mentions', t['co']), ('18 Q4 Organisations', t['org']), ('19 Q4 Individual brands', t['brand_rank']),
              ('20 Data-driven topics', t['topics'])]
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        for name, frame in sheets:
            frame = frame.copy()
            frame.columns = [str(c) for c in frame.columns]
            frame.round(2).to_excel(writer, sheet_name=name[:31], index=False)
            sheet = writer.sheets[name[:31]]
            sheet.freeze_panes = 'B2'
            for column in sheet.columns:
                width = max(len(str(c.value or '')) for c in column[:200])
                sheet.column_dimensions[column[0].column_letter].width = min(max(10, width+2), 70)


if __name__ == '__main__':
    main()
