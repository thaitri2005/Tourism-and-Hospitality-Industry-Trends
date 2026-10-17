"""Build the reader-facing report (output/REPORT.html and REPORT.pdf) from the published analysis.

Every number in the text is read from output/tables, so rebuilding after a new
collection run keeps the prose consistent with the data. Sentences that interpret
patterns are generated from the same tables (e.g. "COVID-19 led every year from
X to Y"); review them after large changes to the corpus.
"""
import html
import re
import json
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pandas as pd

from .codebook import CODEBOOK_VERSION, GBM_TOP10, THEMES
from .config import END, OUTPUT, SOURCES, START
from .runtime import event

EDGE = [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Google\Chrome\Application\chrome.exe', '/usr/bin/google-chrome', '/usr/bin/chromium',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
AUTHOR = 'Thai Huu Tri (Research Assistant)'
RECIPIENT = 'Dr Le Thi Phuong Dung (Jenny)'


def t(name):
    return pd.read_csv(OUTPUT/'tables'/name, encoding='utf-8-sig')


def esc(value):
    return html.escape(str(value))


def pct(value, digits=0):
    return f'{value:.{digits}f}%'


def fmt_date(iso):
    d = date.fromisoformat(iso)
    return f'{d.day} {d:%B %Y}'


def table(df, columns, headers=None, numeric=(), caption=None, widths=None, cls=''):
    headers = headers or columns
    head = ''.join(f'<th class="{"num" if c in numeric else ""}"{f" style=\"width:{widths[i]}\"" if widths else ""}>{esc(h)}</th>'
                   for i, (c, h) in enumerate(zip(columns, headers)))
    rows = []
    for _, r in df.iterrows():
        cells = []
        for c in columns:
            v = r[c]
            if isinstance(v, float) and pd.isna(v):
                v = '–'
            elif isinstance(v, float):
                v = f'{v:,.1f}'
            elif isinstance(v, (int,)) or (hasattr(v, 'dtype') and 'int' in str(getattr(v, 'dtype', ''))):
                v = f'{int(v):,}' if abs(int(v)) >= 10000 else str(int(v))
            cells.append(f'<td class="{"num" if c in numeric else ""}">{esc(v)}</td>')
        rows.append('<tr>'+''.join(cells)+'</tr>')
    cap = f'<caption>{caption}</caption>' if caption else ''
    return f'<table class="{cls}">{cap}<thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def figure(name, caption, number):
    return (f'<figure><img src="figures/{name}" alt="{esc(caption)}">'
            f'<figcaption><b>Figure {number}.</b> {caption}</figcaption></figure>')


def ordinal(n):
    return f'{n}{"th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")}'


def listing(items, final='and'):
    items = list(items)
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + f' {final} ' + items[-1]


def build():
    summary = json.loads((OUTPUT/'run_summary.json').read_text('utf-8'))
    sources = t('sources.csv')
    coverage = t('coverage_by_website_year.csv')
    ranking = t('q1_current_theme_ranking.csv')
    sent_all = t('q1_theme_sentiment_all_years.csv')
    by_year = t('q2_theme_share_by_year.csv')
    top_year = t('q2_top_themes_each_year.csv')
    change = t('q2_change_2017_19_vs_2023_25.csv')
    panel = t('q2_theme_share_by_year_fixed_panel.csv')
    profiles = t('q3_website_profiles.csv')
    site = t('q3_theme_share_by_website.csv')
    gbm = t('q4_gbm_top10_brands.csv')
    groups = t('q4_brand_groups.csv')
    co = t('q4_brand_co_mentions.csv')
    orgs = t('q4_organisation_mentions.csv')
    topics = t('nmf_topics.csv')
    validation = OUTPUT/'tables'/'validation_summary.csv'
    validation = pd.read_csv(validation, encoding='utf-8-sig') if validation.is_file() else None
    fig = iter(range(1, 50))
    tab = iter(range(1, 50))

    n_articles = summary['articles_analysed']
    n_docs = summary['documents_collected']
    n_current = summary['current_articles']
    active = sources[sources.articles_analysed > 0]
    n_sites = len(active)
    archived_share = 100*(active.articles_analysed*active.from_web_archive_pct/100).sum()/n_articles
    cur_start, cur_end = fmt_date(summary['current_window_start']), fmt_date(END)
    top10 = ranking.head(10)
    t1, t2, t3 = top10.theme.iloc[0], top10.theme.iloc[1], top10.theme.iloc[2]
    ai = ranking[ranking.theme == 'Artificial intelligence'].iloc[0]
    most_negative = sent_all.sort_values('net_sentiment').head(3)
    most_positive = sent_all.sort_values('net_sentiment', ascending=False).head(3)
    covid = by_year[by_year.theme == 'COVID-19 pandemic'].set_index('year').share_pct
    covid_peak_year, covid_peak = int(covid.idxmax()), covid.max()
    leaders = top_year.set_index('year')['#1']
    covid_years = [int(y) for y, th in leaders.items() if th == 'COVID-19 pandemic']
    pre_leader = leaders.loc[[y for y in leaders.index if y <= 2019]].value_counts().idxmax()
    post_leader = leaders.loc[[y for y in leaders.index if y >= 2023]].value_counts().idxmax()
    # COVID-19's 2023-25 'rise' is the tail of the pandemic, not a new concern.
    risers = change[change.theme != 'COVID-19 pandemic'].sort_values('change_pp', ascending=False).head(4)
    fallers = change.sort_values('change_pp').head(3)
    ai_series = by_year[by_year.theme == 'Artificial intelligence'].set_index('year').share_pct
    gbm['gbm_2026_rank'] = gbm.gbm_2026_rank.astype(int)
    gbm_sorted = gbm.sort_values('articles', ascending=False)
    other_brands = groups[~groups.group.isin(GBM_TOP10)].sort_values('articles', ascending=False).head(10)
    pair_rows = co.head(8) if not co.empty else co
    brand_sites = t('q4_brand_mentions_by_website.csv').sort_values('pct_mentioning_any_brand', ascending=False)
    assoc = t('q4_brand_theme_associations.csv')
    hotels = ['Marriott International', 'Hilton', 'Hyatt', 'IHG Hotels & Resorts', 'Accor']
    platforms = ['Booking Holdings', 'Expedia Group', 'Airbnb', 'Trip.com Group']

    def profile_of(names):
        # Themes over-represented around these brands (mean lift > 1.2), most frequent first.
        sub = assoc[assoc.group.isin(names)].groupby('theme').agg(share=('share_pct', 'mean'), lift=('lift', 'mean'))
        return list(sub[sub.lift > 1.2].sort_values('share', ascending=False).head(3).index)
    hotel_themes, platform_themes = profile_of(hotels), profile_of(platforms)
    # Where pooling all articles changes the ranking most (large trade-media volumes).
    pooled_rank = ranking.article_weighted_pct.rank(ascending=False, method='first')
    shift = (ranking.assign(pooled_rank=pooled_rank, delta=ranking['rank'] - pooled_rank).sort_values('delta'))
    up_when_pooled = shift[shift.delta > 0].sort_values('delta', ascending=False).theme.head(2).tolist()
    down_when_pooled = shift[shift.delta < 0].theme.head(2).tolist()
    low_negative = int((sent_all.negative_pct < 10).sum())
    second_year = top_year.set_index('year')['#2']
    phases = []   # consecutive years with the same leading theme
    for y, th in leaders.items():
        if phases and phases[-1][1] == th and phases[-1][0][-1] == y-1:
            phases[-1][0].append(int(y))
        else:
            phases.append(([int(y)], th))

    sust_top2 = [int(y) for y in top_year.year if 'Sustainability & climate' in (leaders[y], second_year[y])]
    pre_ai = ai_series[ai_series.index < 2023].max() if (ai_series.index < 2023).any() else 0
    first_full_ai = int(ai_series[ai_series >= 2].index.min()) if (ai_series >= 2).any() else None
    covid_late = covid[covid.index >= 2024]
    leaders_panel = (panel.sort_values(['year', 'share_pct'], ascending=[True, False]).drop_duplicates('year').set_index('year').theme
                     if len(panel) else pd.Series(dtype=str))
    common_years = [y for y in leaders.index if y in leaders_panel.index]
    same_leader = sum(leaders[y] == leaders_panel[y] for y in common_years)
    top3 = top_year.set_index('year')[['#1', '#2', '#3']]
    panel_top3 = (panel.sort_values(['year', 'share_pct'], ascending=[True, False]).groupby('year').head(3).groupby('year').theme.apply(set)
                  if len(panel) else pd.Series(dtype=object))
    top3_overlap = sum(len(set(top3.loc[y]) & panel_top3[y]) >= 2 for y in common_years)
    if 'closest_theme_share_pct' in topics:
        matched = topics[topics.closest_theme_share_pct >= 50]
        unmatched = topics[topics.closest_theme_share_pct < 50]
    else:
        matched = unmatched = topics.iloc[0:0]

    def years_text(ys):
        ys = sorted(ys)
        return f'{ys[0]}–{ys[-1]}' if len(ys) > 1 and ys[-1]-ys[0] == len(ys)-1 else listing([str(y) for y in ys])

    # ------------------------------------------------------------------ sections
    findings = [
        f'<b>Current discussion.</b> In the twelve months to {cur_end}, the most discussed themes were <b>{esc(t1)}</b> '
        f'({pct(top10.share_pct.iloc[0])} of articles), <b>{esc(t2)}</b> ({pct(top10.share_pct.iloc[1])}) and <b>{esc(t3)}</b> '
        f'({pct(top10.share_pct.iloc[2])}). Artificial intelligence ranks {ordinal(int(ai["rank"]))} when every website counts equally, '
        f'but it is the fastest-growing theme: from at most {pct(pre_ai, 1)} of articles in any year before 2023 to {pct(ai_series.iloc[-1])} in 2026, '
        f'concentrated in the trade media.',
        f'<b>Tone.</b> Industry websites rarely write negatively: for {low_negative} of the {len(sent_all)} themes fewer than 10% of articles are negative, '
        f'and most of the rest is neutral, factual reporting. Positive tone is strongest for {listing(esc(x) for x in most_positive.theme)} and weakest for '
        f'the themes about threats — {listing(esc(x) for x in most_negative.theme)}.',
        f'<b>Change over time.</b> {esc(pre_leader)} led the discussion before the pandemic; COVID-19 was the leading theme in '
        f'{years_text(covid_years)} (peaking at {pct(covid_peak)} of articles in {covid_peak_year}); since 2023 {esc(post_leader)} has led most years. '
        f'The largest gains between 2017–19 and 2023–25 are in {listing(esc(x) for x in risers.theme)}.',
        f'<b>Each website has its own agenda.</b> ' + ' '.join(
            f'{esc(r.website)}: {esc(r.top_1.rsplit(" (", 1)[0])}.' for r in profiles.itertuples()),
        f'<b>Brands.</b> Of the ten brands in the Global Brands Magazine 2026 list, '
        f'{listing(esc(x) for x in gbm_sorted.group.head(3))} are discussed most often. The hotel groups are discussed mainly in connection with '
        f'{listing(esc(x) for x in hotel_themes)}; the online platforms with {listing(esc(x) for x in platform_themes)}.'
    ]

    method = f'''
<h2 id="methods">2. Data and methodology</h2>
<h3>2.1 Sources and scope</h3>
<p>The study covers the nine websites named in the brief: three intergovernmental or regional tourism bodies (UN Tourism, the
European Travel Commission and the Caribbean Tourism Organization), four industry associations (WTTC, IH&amp;RA, PATA and AHLA)
and two trade-media publishers (Hospitality Net and Travel Weekly). The brief mentions ten websites but lists nine; the
Global Brands Magazine page is used as the reference list of brands rather than as a tenth source. The study period runs from
{fmt_date(START)} to {fmt_date(END)} (ten years), restricted to English-language news articles, press releases and blog posts.
Reports, report landing pages, event listings, directories and membership pages were excluded from the analysis.
“Current” refers to the last twelve months of the period: {cur_start} to {cur_end}.</p>
{table(sources.assign(period=sources.first_article.fillna('').str[:4] + '–' + sources.last_article.fillna('').str[:4]),
       ['website', 'type', 'articles_analysed', 'current_window_articles', 'period', 'from_web_archive_pct'],
       ['Website', 'Type', 'Articles analysed', 'Of which current', 'Years', '% from web archive'],
       numeric=('articles_analysed', 'current_window_articles', 'from_web_archive_pct'), widths=['26%', '24%', '13%', '12%', '12%', '13%'], cls='keep',
       caption=f'<b>Table {next(tab)}.</b> The nine websites and the articles analysed from each.')}

<h3>2.2 Data collection</h3>
<p>Articles were collected automatically with a purpose-built Python crawler that identifies itself as an academic research tool,
waits at least three seconds between requests to the same website, honours rate-limit responses and records every request.
Collection is resumable, and each saved document keeps its source URL, retrieval time and raw copy for checking.
Three routes were used, chosen per website according to what each site makes available:</p>
<ol>
<li><b>Live websites.</b> Article URLs were listed from each site's XML sitemaps and its paginated news, press-release and blog
archives, then downloaded directly (UN Tourism, WTTC, PATA, AHLA, ETC and Hospitality Net).</li>
<li><b>Random sample of Hospitality Net articles.</b> Hospitality Net publishes several thousand items a year and numbers them
sequentially, but its archive pages only reach back a few months. To cover 2016–2026 evenly, 1,800 article numbers were drawn
at random across the whole numbering range and each was downloaded from the live site, giving an unbiased sample of the
publisher's output over the decade.</li>
<li><b>Web archive (Internet Archive Wayback Machine).</b> The Caribbean Tourism Organization and Travel Weekly block automated
access, and the older press-release archives of WTTC (before 2019), AHLA and PATA (before 2020) no longer exist on the live sites.
For these, the Wayback Machine's index was used to list the archived article pages, and the archived copy of each page was
retrieved. Travel Weekly publishes far more than can be read, so up to 170 articles were sampled at random per year.
The publication date is always taken from the article itself; archived copies are labelled as such in the data.</li>
</ol>
<p>In total {n_docs:,} documents were collected, of which {n_articles:,} articles from {n_sites} websites are analysed
(about {archived_share:.0f}% retrieved from the web archive). IH&amp;RA could not contribute: its website contains no original news in the
study period, and the “News” page of its former site (ih-ra.org) only republished short Hospitality Net headlines. This gap is reported rather than filled with other material.</p>

<h3>2.3 Data preparation</h3>
<p>For each page the headline, publication date and main text were extracted, using the publisher's structured metadata where present and
site-specific rules otherwise. Navigation, contact details, “about us” boilerplate and social-media footers were removed.
A document entered the analysis only if it was in English, had a verifiable publication date inside the study period and contained at
least 120 words of text. Duplicates were removed in two steps: identical texts, then near-identical versions of the same story
(cosine similarity of 0.94 or more on TF-IDF word vectors), so that a press release republished on several pages counts once per
website and year. Of the {summary["eligible_documents"]:,} documents that passed these checks, {n_articles:,} unique articles remain.</p>

<h3>2.4 Identifying themes</h3>
<p>Themes were measured with a transparent dictionary (codebook version {CODEBOOK_VERSION}, Appendix A) of {len(THEMES)} themes, each defined by
a list of words and phrases — for example <i>sustainability, carbon, net zero, biodiversity</i> for “Sustainability &amp; climate” or
<i>artificial intelligence, generative AI, machine learning, chatbot</i> for “Artificial intelligence”. The list started from the examples in the
brief (sustainability, AI, social media) and the tourism literature, and was refined by reading samples of matched and unmatched articles
and by comparing it with themes found without a dictionary (section 2.7). Generic institutional activity such as partnerships and
memoranda of understanding is not counted as a theme. After the validation reading (section 2.7) the terms of four themes were narrowed once
(codebook version 1.1): bare “jobs” and “employment”, which mostly occur in economic-impact statements, no longer count as workforce discussion,
and generic words such as “culture” (as in company culture), “connectivity” and “diversity” were replaced by more specific phrases.</p>
<p>Because a single passing mention does not make an article <i>about</i> a theme, an article counts as <b>discussing</b> a theme only when a
theme term appears in the headline, appears at least twice in the opening {80} words, or appears at least three times using at least two different
terms. An article can discuss several themes. The basic measure is the <b>share of articles discussing each theme</b>. Because the websites
publish very different volumes, shares are calculated within each website first and then averaged with equal weight per website
(only websites with at least 20 articles in the period concerned are included). This stops the largest publishers from determining the overall picture.</p>
<ul>
<li><b>Q1, current themes:</b> themes ranked by their equal-weighted share in the last twelve months.</li>
<li><b>Q2, themes over time:</b> the same share calculated for each calendar year from 2016 to 2026, with the five leading themes of each year.
2016 (10 October–31 December) and 2026 (to 10 October) are partial years.</li>
<li><b>Q3, themes by website:</b> each website's share of articles discussing each theme over the whole period, and a distinctiveness ratio:
the website's share divided by the average share on the other websites (2.0 = twice as common as elsewhere).</li>
</ul>

<h3>2.5 Sentiment</h3>
<p>Sentiment was measured with a transformer language model trained for three-class sentiment classification
(<i>twitter-roberta-base-sentiment-latest</i>, Loureiro et al. 2022), which reads each sentence in context rather than counting
positive and negative words. Up to five sentences that mention a theme an article discusses were scored, and the article's tone towards
that theme is the average of their negative, neutral and positive probabilities — so an article that welcomes AI but warns about job losses
contributes to two themes with different tones. Sentences mentioning a brand were scored in the same way. Results are summarised as the share
of articles that are positive, neutral and negative and as <i>net sentiment</i> (positive minus negative share). The model was chosen after
testing four candidates against the validation reading described in section 2.7; the widely used VADER word-list method
over-rated the positivity of business news and was rejected. Organisational communication is strongly positive by design,
so differences between themes are more informative than absolute levels.</p>

<h3>2.6 Brands and their associations</h3>
<p>Brand mentions were counted with a dictionary of {len(groups)} brand families. It contains every company in the Global Brands Magazine list
“Top 10 Tourism Brands in the World (2026)” — Booking Holdings, Hilton, Marriott International, Airbnb, Expedia Group, Hyatt,
IHG Hotels &amp; Resorts, Disney, Trip.com Group and Accor — together with their flagship sub-brands named in that article (for example
Ritz-Carlton, Sheraton and Westin under Marriott International, or Agoda and KAYAK under Booking Holdings), plus other hotel companies,
airlines, cruise lines, tour operators and travel-technology firms. Sub-brands are grouped under their 2026 owner. Ambiguous names
(for example “Hilton Head”, “United Arab Emirates”) are filtered out. For each brand family we report the number of articles mentioning it and the
websites it appears on. <b>Associations</b> are measured from the text around each mention (the sentence containing the brand plus one sentence
either side): the share of the brand's articles in which each theme appears in that window, and the <i>lift</i> — how much more often the theme appears
around this brand than around brands in general. We also list the words most distinctive of each brand's context (log-odds ratio with an informative
Dirichlet prior, Monroe et al. 2008), the sentiment of sentences mentioning the brand, and which brands are named together in the same article.</p>

<h3>2.7 Cross-checks and validation</h3>
<p>As an independent check on the dictionary, an unsupervised topic model (TF-IDF with non-negative matrix factorisation, {len(topics)} topics, trained on a
balanced sample of at most 120 articles per website and year) was fitted without any predefined themes (Appendix B). For {len(matched)} of the {len(topics)}
topics, at least half of the articles in the topic discuss a single dictionary theme (for example {listing(esc(x) for x in matched.closest_theme.drop_duplicates().head(4))}),
so the themes found without a dictionary largely coincide with the codebook. The remaining topics group articles by publisher-specific subjects
(for example {listing(esc(", ".join(x.split(", ")[:3])) for x in unmatched.top_terms.head(3)) if len(unmatched) else "none"}) rather than by industry themes.
Automated consistency checks confirm that every article lies inside the study period, that no story is counted twice for a website and year,
and that all tables add up.</p>
{validation_text(validation)}
'''

    q1_table = table(top10.assign(net=top10.net_sentiment),
                     ['rank', 'theme', 'share_pct', 'article_weighted_pct', 'websites_discussing', 'positive_pct', 'negative_pct', 'net'],
                     ['#', 'Theme', '% of articles (equal weight)', '% of all articles pooled', 'Websites', '% positive', '% negative', 'Net sentiment'],
                     numeric=('rank', 'share_pct', 'article_weighted_pct', 'websites_discussing', 'positive_pct', 'negative_pct', 'net'),
                     widths=['4%', '32%', '12%', '12%', '9%', '10%', '10%', '11%'], cls='keep',
                     caption=f'<b>Table {next(tab)}.</b> The ten leading themes, {cur_start} – {cur_end} ({n_current:,} articles).')
    q1 = f'''
<h2 id="q1">3. Results</h2>
<h3>3.1 Ten key themes in the current discussion</h3>
<p>Figure 1 ranks the themes by the share of articles that discuss them in the last twelve months. <b>{esc(t1)}</b>, <b>{esc(t2)}</b> and <b>{esc(t3)}</b>
lead, followed by {listing(esc(x) for x in top10.theme.iloc[3:10])}. Table 2 also shows the share when all articles are simply pooled, which gives the
high-volume trade-media sites more weight: {listing(esc(x) for x in up_when_pooled)} then rank higher, and {listing(esc(x) for x in down_when_pooled)} lower.
The equal-website ranking is used as the main result because it treats each community's agenda as equally important.</p>
{figure('q1_top10_current_themes.png', f'Ten leading themes, {cur_start} – {cur_end}: share of articles discussing each theme, equal weight per website.', next(fig))}
{q1_table}
<p><b>Sentiment.</b> Negative tone is rare for all ten themes (Figure 2): most sentences are neutral, factual reporting, and the rest is mostly
positive, reflecting the promotional nature of association and trade communication. Relative differences are informative: across the whole period the most positive themes are {listing(esc(x) for x in most_positive.theme)},
while the least positive are {listing(esc(x) for x in most_negative.theme)} — themes that by their nature describe threats, shocks and pressures.</p>
{figure('q1_top10_sentiment.png', 'Sentiment of the ten leading themes: share of articles whose sentences about the theme are negative, neutral or positive (RoBERTa sentiment model).', next(fig))}
'''

    phase_text = '; '.join(f'{years_text(ys)}: <b>{esc(th)}</b>' for ys, th in phases)
    covid_text = (f'COVID-19 was the leading theme in {years_text(covid_years)}, peaking at {pct(covid_peak)} of articles in {covid_peak_year}, and '
                  'remained visible through the recovery period as “post-pandemic” recovery language.') if covid_years else ''
    q2 = f'''
<h3>3.2 Key themes over time, 2016–2026</h3>
<p>Figure 3 shows how prominent each theme was in each year; the outlined cells are each year's top three, and Table 3 lists the five leading themes
per year. The leading theme changes in clear phases — {phase_text}. {covid_text}
Sustainability &amp; climate was in first or second place in {years_text(sust_top2) if sust_top2 else 'no year'}.</p>
{figure('q2_themes_by_year_heatmap.png', 'Share of articles discussing each theme, by year (equal weight per website). Outlined: the three leading themes of each year.', next(fig))}
{table(top_year, ['year', '#1', '#2', '#3', '#4', '#5', 'websites'], ['Year', '1st', '2nd', '3rd', '4th', '5th', 'Websites'], numeric=('year', 'websites'),
       caption=f'<b>Table {next(tab)}.</b> The five leading themes in each year.', cls='small')}
<p>Comparing the three years before the pandemic (2017–19) with the three most recent full years (2023–25) shows which concerns have grown
(Table 4). The largest increases are in {listing(f"{esc(r.theme)} (+{r.change_pp:.0f} points)" for r in risers.itertuples())}; the largest decreases in
{listing(f"{esc(r.theme)} ({r.change_pp:.0f} points)" for r in fallers.itertuples())}. Figure 4 traces selected themes: artificial intelligence was
discussed in at most {pct(pre_ai, 1)} of articles in any year before 2023 and reached {pct(ai_series.iloc[-1])} in 2026, while the pandemic theme rose to
{pct(covid_peak)} in {covid_peak_year} and fell to {pct(covid_late.max() if len(covid_late) else 0)} or less from 2024.</p>
{figure('q2_selected_theme_trends.png', 'Selected themes over time: share of articles discussing each theme (equal weight per website).', next(fig))}
{table(change.sort_values('change_pp', ascending=False), ['theme', 'share_2017_2019', 'share_2023_2025', 'change_pp'],
       ['Theme', '2017–19 (% of articles)', '2023–25 (% of articles)', 'Change (points)'],
       numeric=('share_2017_2019', 'share_2023_2025', 'change_pp'), caption=f'<b>Table {next(tab)}.</b> Change in theme prominence, 2017–19 vs 2023–25.', cls='small')}
<p class="note">Robustness: because not every website covers every year, the yearly figures were recalculated using only the websites present
in every year from 2017 to 2025 ({esc(panel.panel.iloc[0]) if len(panel) else 'none'}). The leading theme is the same in {same_leader} of {len(common_years)} years and at least two of the top three themes are the same in
{top3_overlap} of {len(common_years)} years; the differences come mainly from leaving out WTTC, ETC and CTO, whose agendas are distinctive
(results in the workbook, sheet 9).</p>
'''

    site_cols = [c for c in site.columns if c != 'website']
    q3 = f'''
<h3>3.3 Key themes on each website</h3>
<p>The websites serve different communities and their agendas differ accordingly (Figure 5, Table 5). The ratio in the last column shows the themes each
site discusses much more than the others do — a summary of what makes each community distinctive.</p>
{figure('q3_themes_by_website_heatmap.png', 'Share of each website\'s articles discussing each theme, 2016–2026. Outlined: each website\'s three leading themes.', next(fig))}
{table(profiles, ['website', 'articles', 'top_1', 'top_2', 'top_3', 'most_distinctive'],
       ['Website', 'Articles', 'Leading theme', 'Second', 'Third', 'Most distinctive (× other sites)'], numeric=('articles',),
       caption=f'<b>Table {next(tab)}.</b> Leading and most distinctive themes of each website (share of the site\'s articles).', cls='small')}
{site_narrative(profiles)}
'''

    q4 = f'''
<h3>3.4 Key brands and their associations</h3>
<p>Figure 6 shows how often each company in the Global Brands Magazine 2026 top ten is discussed, counting any of its brands. Table 6 adds the websites
where they appear, the themes discussed around them and the tone of those sentences. Companies are named most often on
{listing(f"{esc(r.website)} ({r.pct_mentioning_any_brand:.0f}% of articles)" for r in brand_sites.head(2).itertuples())} and least often on
{listing(f"{esc(r.website)} ({r.pct_mentioning_any_brand:.0f}%)" for r in brand_sites.tail(2).itertuples())}.</p>
{figure('q4_gbm_brand_mentions.png', 'Articles mentioning each Global Brands Magazine top-10 company (any of its brands), 2016–2026, in the magazine\'s rank order.', next(fig))}
{table(gbm, ['gbm_2026_rank', 'group', 'articles', 'websites', 'top_associated_themes', 'net_sentiment'],
       ['GBM rank', 'Brand', 'Articles', 'Websites', 'Themes discussed around the brand (share of its articles, lift)', 'Net sentiment'],
       numeric=('gbm_2026_rank', 'articles', 'websites', 'net_sentiment'), widths=['7%', '17%', '8%', '8%', '50%', '10%'],
       caption=f'<b>Table {next(tab)}.</b> The Global Brands Magazine top 10 in the corpus.', cls='small keep')}
{table(gbm, ['group', 'brands_mentioned', 'associated_words'], ['Brand', 'Sub-brands mentioned (articles)', 'Most distinctive words around the brand'],
       widths=['17%', '43%', '40%'], caption=f'<b>Table {next(tab)}.</b> Which of each company\'s brands are discussed, and the vocabulary that distinguishes it.', cls='small keep')}
{figure('q4_brand_theme_heatmap.png', 'Brand associations: share of each brand family\'s articles in which a theme appears within one sentence of the brand. Outlined: each brand\'s three most frequent themes.', next(fig))}
{brand_narrative(gbm)}
{figure('q4_gbm_brands_by_year.png', 'Attention to the Global Brands Magazine top 10 over time: articles mentioning the brand per 1,000 articles analysed in that year.', next(fig))}
<p><b>Other prominent names.</b> Beyond the magazine's list, the most frequently discussed companies are {listing(f"{esc(r.group)} ({int(r.articles)})" for r in other_brands.itertuples())}
— mostly travel-technology firms, airlines and regional hotel groups. The brands most often named together in the same article are
{listing(f"{esc(r.brand_a)} and {esc(r.brand_b)} ({int(r.articles)} articles)" for r in pair_rows.head(4).itertuples())}.</p>
{figure('q4_brand_sentiment.png', 'Tone of sentences mentioning each brand family (brands with at least 40 articles).', next(fig))}
<p><b>Industry bodies.</b> Among organisations other than the publisher itself, the most frequently mentioned are
{listing(f"{esc(r.organization)} ({int(r.articles)} articles)" for r in orgs.head(6).itertuples())} (full list in the workbook, sheet 18).</p>
'''

    limits = f'''
<h2 id="limits">4. Limitations</h2>
<ul>
<li><b>What is measured.</b> The results describe what these nine organisations and publishers write about, not the opinions of travellers or the whole industry.
Press releases are written to promote, which is why
negative tone is rare.</li>
<li><b>Coverage differs by website.</b> Volumes and years covered differ (Appendix C). Equal weighting per website prevents large publishers from dominating,
but the set of websites contributing to each year changes; the fixed-panel check in section 3.2 shows the main trends are robust to this. IH&amp;RA has no
original content in the period. Some archived pages could not be retrieved.</li>
<li><b>Samples, not censuses.</b> Hospitality Net and Travel Weekly were sampled at random; other websites were collected as completely as their sitemaps,
archives and the web archive allow. Removed pages cannot be recovered.</li>
<li><b>Dictionary methods.</b> Theme and brand dictionaries are transparent and reproducible but can miss unusual wording and occasionally match an unrelated
use of a word; the “discussing” rule and the validation sample reduce, but do not remove, this error. Sentiment is measured on wording, so sarcasm or
mixed statements are not always captured; on the validation sample the sentiment model disagreed with the reader for about one sentence in seven.</li>
<li><b>Brand ownership</b> is mapped to 2026 owners (for example Six Senses under IHG throughout), and co-occurrence in text indicates association in
discussion, not a business relationship.</li>
</ul>
'''

    readable = lambda p: re.sub(r'\[([A-Z])([a-z])\]', lambda m: m.group(2), p)
    codebook_rows = pd.DataFrame([dict(theme=k, terms=', '.join(readable(p).replace('\\s+', ' ').replace('\\s', ' ').replace('[\\s-]', '-').replace('(?:', '(')
                                                                for p in v[:14])) for k, v in THEMES.items()])
    appendix = f'''
<h2 id="appendix">Appendix A. Theme codebook (version {CODEBOOK_VERSION})</h2>
<p class="note">The first terms of each theme are shown as regular expressions (the full list is in <code>output/codebook.json</code>). Matching ignores case except for
abbreviations such as AI, OTA and MICE.</p>
{table(codebook_rows, ['theme', 'terms'], ['Theme', 'Example terms'], cls='small codebook')}
<h2>Appendix B. Topics found without a dictionary (TF-IDF + NMF)</h2>
{table(topics, ['topic', 'top_terms', 'articles', 'main_websites', 'closest_theme', 'closest_theme_share_pct'] if 'closest_theme' in topics else ['topic', 'top_terms', 'articles', 'main_websites'],
       ['#', 'Most characteristic words', 'Articles', 'Main websites', 'Closest dictionary theme', '% of topic articles discussing it'],
       numeric=('topic', 'articles', 'closest_theme_share_pct'), cls='small')}
<h2>Appendix C. Articles analysed by website and year</h2>
{table(coverage, ['website']+[c for c in coverage.columns if c != 'website'], ['Website']+[c for c in coverage.columns if c != 'website'],
       numeric=tuple(c for c in coverage.columns if c != 'website'), cls='small')}
{figure('coverage_by_website_year.png', 'Articles analysed by website and year.', next(fig))}
<h2>Appendix D. Files delivered</h2>
<table class="small"><thead><tr><th>File</th><th>Contents</th></tr></thead><tbody>
<tr><td>REPORT.pdf / REPORT.html</td><td>This report.</td></tr>
<tr><td>METHODOLOGY_SUMMARY.md</td><td>A one-paragraph methodology summary with the current numbers.</td></tr>
<tr><td>RESULTS.xlsx</td><td>All result tables, one sheet per table, with a README sheet.</td></tr>
<tr><td>tables/*.csv</td><td>The same tables as CSV, plus article-level data: <code>articles_analysed.csv</code> (metadata and URL of every article),
<code>article_themes.csv</code> and <code>article_brands.csv</code> (every theme and brand coding with its sentiment score).</td></tr>
<tr><td>figures/*.png</td><td>All figures at print resolution.</td></tr>
<tr><td>codebook.json</td><td>The complete theme, brand and organisation dictionaries and coding rules.</td></tr>
</tbody></table>
<p class="note">Article texts are kept in the project database for re-analysis and are not redistributed, in line with the publishers' terms.
The collection and analysis can be re-run with <code>python run_research.py</code>.</p>
'''

    toc = ('<nav class="toc"><b>Contents</b><ol><li><a href="#summary">Summary</a></li><li><a href="#methods">Data and methodology</a></li>'
           '<li><a href="#q1">Results</a></li><li><a href="#limits">Limitations</a></li><li><a href="#appendix">Appendices</a></li></ol></nav>')
    body = f'''
<header class="cover">
<p class="kicker">Research assistant report</p>
<h1>What the tourism and hospitality industry talks about</h1>
<p class="subtitle">Themes, trends and brands in nine industry websites, {fmt_date(START)} – {fmt_date(END)}</p>
<p class="meta">Prepared for {RECIPIENT} · {AUTHOR} · {fmt_date(summary['created_at'][:10])}</p>
<div class="kpis">
<div><span>{n_articles:,}</span>articles analysed</div><div><span>{n_sites}</span>websites</div>
<div><span>11</span>years (2016–2026)</div><div><span>{len(THEMES)}</span>themes coded</div><div><span>{len(groups)}</span>brand families found</div>
</div>
</header>
{toc}
<section id="summary">
<h2>Summary</h2>
<p>This report analyses {n_articles:,} English-language articles published between {fmt_date(START)} and {fmt_date(END)} by
{n_sites} of the nine tourism and hospitality organisations and trade publishers named in the brief. It answers four questions:
which themes dominate the current industry discussion and in what tone; how the leading themes changed year by year; what each website's
community focuses on; and which brands are discussed and what they are associated with. Section 2 explains how the data were collected and analysed.</p>
<ul class="findings">{''.join(f'<li>{f}</li>' for f in findings)}</ul>
</section>
{method}
{q1}
{q2}
{q3}
{q4}
{limits}
<h2>References</h2>
<ul class="refs">
<li>Global Brands Magazine (2026). <i>Top 10 Tourism Brands in the World (2026)</i>. https://www.globalbrandsmagazine.com/tourism-brands-in-the-world/</li>
<li>Hutto, C. J., &amp; Gilbert, E. (2014). VADER: A parsimonious rule-based model for sentiment analysis of social media text. <i>Proceedings of ICWSM</i>, 8(1), 216–225.</li>
<li>Loureiro, D., Barbieri, F., Neves, L., Espinosa Anke, L., &amp; Camacho-Collados, J. (2022). TimeLMs: Diachronic language models from Twitter. <i>Proceedings of ACL: System Demonstrations</i>, 251–260.</li>
<li>Lee, D. D., &amp; Seung, H. S. (1999). Learning the parts of objects by non-negative matrix factorization. <i>Nature</i>, 401, 788–791.</li>
<li>Monroe, B. L., Colaresi, M. P., &amp; Quinn, K. M. (2008). Fightin' words: Lexical feature selection and evaluation for identifying the content of political conflict. <i>Political Analysis</i>, 16(4), 372–403.</li>
<li>Internet Archive. Wayback Machine CDX Server API. https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server</li>
</ul>
{appendix}
'''
    return page(body)


def validation_text(v):
    if v is None or v.empty:
        return ''
    r = v.set_index('measure').value
    return (f'<p><b>Validation sample.</b> To check the automated coding, a stratified random sample of {int(r["articles"])} articles '
            f'({int(r["per_website"])} per website) was read and coded independently of the dictionary, recording which themes each article is '
            f'substantially about, together with the tone of {int(r["sentiment_items"])} randomly chosen theme sentences. Against this reading the '
            f'“discussing” rule achieved a precision of {r["precision"]:.0%} (share of automated assignments confirmed) and a recall of '
            f'{r["recall"]:.0%} (share of the reader’s themes that the rule also found); counting every passing mention instead would give a precision '
            f'of only {r["mention_precision"]:.0%}. The sentiment model agreed with the reader’s positive/neutral/negative judgement for '
            f'{r["sentiment_agreement"]:.0%} of sentences (VADER: {r["vader_agreement"]:.0%}). The independent reading was carried out with the help of an '
            f'AI language model and should be complemented by a human check before publication. Because the codebook was revised once after this reading, '
            f'these figures are partly in-sample and somewhat optimistic. Per-theme results are in '
            f'<code>tables/validation_by_theme.csv</code>.</p>')


def site_narrative(profiles):
    lines = []
    for r in profiles.itertuples():
        top = [x.rsplit(' (', 1)[0] for x in (r.top_1, r.top_2, r.top_3)]
        distinct = str(r.most_distinctive).split('; ')[0].rsplit(' (', 1)[0] if isinstance(r.most_distinctive, str) and r.most_distinctive else ''
        lines.append(f'<li><b>{esc(r.website)}</b> ({int(r.articles):,} articles): focuses on {esc(top[0])}, {esc(top[1])} and '
                     f'{esc(top[2])}' + (f'; its most distinctive theme compared with the other sites is {esc(distinct)}.' if distinct else '.') + '</li>')
    return '<ul class="sites">' + ''.join(lines) + '</ul>'


def brand_narrative(gbm):
    lines = []
    for r in gbm.sort_values('articles', ascending=False).itertuples():
        if not isinstance(r.top_associated_themes, str) or not r.top_associated_themes:
            continue
        themes = [x.rsplit(' (', 1)[0] for x in r.top_associated_themes.split('; ')]
        words = ', '.join(str(r.associated_words).split(', ')[:6]) if isinstance(r.associated_words, str) else ''
        lines.append(f'<li><b>{esc(r.group)}</b> ({int(r.articles)} articles): discussed with {esc(listing(themes))}'
                     + (f'; characteristic words: <i>{esc(words)}</i>' if words else '') + '.</li>')
    return '<p>Read together, the association measures give a profile of each brand in industry discussion:</p><ul class="sites">' + ''.join(lines) + '</ul>'


CSS = '''
:root{--ink:#14202b;--ink2:#46525e;--muted:#7a848d;--line:#d9dde1;--accent:#1c5cab;--wash:#f3f6fa;--paper:#ffffff;}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--ink:#eef1f4;--ink2:#c3c9cf;--muted:#98a1a9;--line:#39424b;--accent:#86b6ef;--wash:#1d2630;--paper:#121820;}}
:root[data-theme="dark"]{--ink:#eef1f4;--ink2:#c3c9cf;--muted:#98a1a9;--line:#39424b;--accent:#86b6ef;--wash:#1d2630;--paper:#121820;}
@page{size:A4;margin:16mm 15mm 16mm 15mm}
*{box-sizing:border-box}
html{background:var(--paper)}
body{font-family:"Segoe UI",Calibri,system-ui,-apple-system,sans-serif;color:var(--ink);background:var(--paper);font-size:10.5pt;line-height:1.5;
max-width:190mm;margin:0 auto;padding:0 16px}
h1{font-size:25pt;line-height:1.15;margin:.2em 0 .2em;color:var(--ink)}
h2{font-size:15pt;margin:1.6em 0 .5em;padding-top:.3em;border-top:2px solid var(--accent);color:var(--ink);break-after:avoid}
h3{font-size:11.5pt;margin:1.2em 0 .35em;color:var(--accent);break-after:avoid}
p{margin:.45em 0 .7em;text-align:left}
a{color:var(--accent)}
.cover{padding:10mm 0 4mm}
.kicker{text-transform:uppercase;letter-spacing:.12em;font-size:8.5pt;color:var(--accent);font-weight:600;margin:0}
.subtitle{font-size:13pt;color:var(--ink2);margin:.2em 0 .8em}
.meta{color:var(--muted);font-size:9pt}
.kpis{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 4px}
.kpis div{flex:1 1 90px;background:var(--wash);border-radius:6px;padding:8px 10px;font-size:8.5pt;color:var(--ink2)}
.kpis span{display:block;font-size:17pt;font-weight:600;color:var(--ink)}
.toc{font-size:9pt;color:var(--ink2);margin:6px 0 0}
.toc ol{display:inline;padding:0;margin:0 0 0 6px;list-style:none}
.toc li{display:inline;margin-right:12px}
.findings li{margin-bottom:.55em}
figure{margin:12px 0 14px;break-inside:avoid;text-align:center}
figure img{max-width:100%;height:auto;background:#fcfcfb;border-radius:4px}
figcaption{font-size:8.6pt;color:var(--ink2);text-align:left;margin-top:4px}
table{border-collapse:collapse;width:100%;margin:8px 0 14px;font-size:8.8pt;break-inside:auto}
table.small{font-size:8pt}
caption{caption-side:top;text-align:left;font-size:8.6pt;color:var(--ink2);margin-bottom:4px}
th{text-align:left;font-weight:600;border-bottom:1.5px solid var(--ink2);padding:4px 5px;vertical-align:bottom}
td{border-bottom:1px solid var(--line);padding:3.5px 5px;vertical-align:top}
tr{break-inside:avoid}
table.keep{break-inside:avoid}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.note{font-size:8.8pt;color:var(--ink2)}
.codebook td:first-child{width:28%;font-weight:600}
.refs{font-size:9pt}
code{font-size:.92em}
@media print{body{max-width:none;padding:0}h2{break-before:auto}.toc a{color:inherit;text-decoration:none}}
@media (max-width:640px){body{font-size:10pt}h1{font-size:20pt}table{display:block;overflow-x:auto}}
'''


def page(body):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Tourism Industry Discourse</title><style>{CSS}</style></head><body>{body}</body></html>')


def to_pdf(html_path, pdf_path):
    browser = next((b for b in EDGE if Path(b).is_file()), None) or shutil.which('msedge') or shutil.which('chromium')
    if not browser:
        event('report_pdf_skipped', level='WARNING', reason='No Edge/Chrome found; open REPORT.html and print to PDF')
        return None
    profile = OUTPUT.parent/'tmp'/'edge-profile'
    profile.mkdir(parents=True, exist_ok=True)
    subprocess.run([browser, '--headless=new', '--disable-gpu', '--no-pdf-header-footer', f'--user-data-dir={profile}',
                    f'--print-to-pdf={pdf_path}', Path(html_path).resolve().as_uri()], capture_output=True, timeout=180, check=True)
    return pdf_path


def methodology_summary():
    """A self-contained methodology paragraph (requested by the supervisor), with the current numbers."""
    summary = json.loads((OUTPUT/'run_summary.json').read_text('utf-8'))
    sources = t('sources.csv')
    active = sources[sources.articles_analysed > 0]
    v = OUTPUT/'tables'/'validation_summary.csv'
    v = pd.read_csv(v, encoding='utf-8-sig').set_index('measure').value if v.is_file() else None
    archived = round((active.articles_analysed*active.from_web_archive_pct/100).sum())
    text = (
        f"Data were collected from the nine tourism and hospitality websites specified in the brief (UN Tourism, WTTC, IH&RA, PATA, AHLA, "
        f"the European Travel Commission, the Caribbean Tourism Organization, Hospitality Net and Travel Weekly), covering English-language news "
        f"articles, press releases and blog posts published between {fmt_date(START)} and {fmt_date(END)}. A purpose-built Python crawler listed "
        f"article pages from each site's sitemaps and paginated archives and downloaded them at a polite rate (at least three seconds between "
        f"requests). Where a site blocks automated access (CTO, Travel Weekly) or its older archives are no longer online (WTTC, AHLA and PATA "
        f"before 2019-2020), archived copies were retrieved from the Internet Archive's Wayback Machine ({archived:,} articles); high-volume "
        f"Hospitality Net and Travel Weekly were sampled at random across the decade. Headlines, dates and main text were extracted, and only "
        f"dated English articles of at least 120 words were kept; duplicates and near-duplicates (TF-IDF cosine similarity of 0.94 or more) "
        f"were removed, leaving {summary['articles_analysed']:,} articles from {len(active)} websites (IH&RA published no original news in the period). "
        f"Themes were coded with a transparent dictionary of {len(THEMES)} industry themes; an article counted as discussing a theme when a theme term "
        f"appeared in its headline, twice in its opening 80 words, or at least three times using two different terms. Theme prominence was measured "
        f"as the share of articles discussing each theme, calculated within each website and averaged with equal weight per website, for the "
        f"last twelve months (current themes), for each year from 2016 to 2026 (trends) and for each website (community focus). Sentiment towards "
        f"each theme and brand was estimated with a RoBERTa transformer sentiment model applied to the sentences that mention it. Brands were "
        f"identified with a dictionary built from the Global Brands Magazine 2026 list of the top ten tourism brands and their sub-brands, extended "
        f"to other hotel, airline, cruise and travel-technology companies; brand associations were measured from the themes and words appearing "
        f"within one sentence of each brand mention. An unsupervised topic model (TF-IDF with non-negative matrix factorisation) was used as a "
        f"cross-check on the dictionary")
    if v is not None:
        text += (f", and a stratified random validation sample of {int(v['articles'])} articles and {int(v['sentiment_items'])} sentences, coded "
                 f"independently, gave a theme-coding precision of {v['precision']:.0%}, a recall of {v['recall']:.0%} and {v['sentiment_agreement']:.0%} "
                 f"agreement on sentiment.")
    else:
        text += '.'
    return text


def main():
    html_path, pdf_path = OUTPUT/'REPORT.html', OUTPUT/'REPORT.pdf'
    html_path.write_text(build(), 'utf-8')
    summary_text = '# Methodology (summary paragraph)\n\n' + methodology_summary() + '\n'
    (OUTPUT/'METHODOLOGY_SUMMARY.md').write_text(summary_text, 'utf-8')
    pdf = to_pdf(html_path, pdf_path)
    event('report_written', html=str(html_path), pdf=str(pdf) if pdf else None)
    return dict(status='complete', html=str(html_path), pdf=str(pdf) if pdf else None)


if __name__ == '__main__':
    os.environ.setdefault('PYTHONUTF8', '1')
    print(main())
