from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUTPUT = ROOT / 'output'
START = '2016-10-10'
END = '2026-10-10'
USER_AGENT = 'TourismResearchPilot/0.1 (academic research; public content only)'

# A registry is deliberately separate from crawler code. Restricted sources are
# audited, but their articles are not automatically downloaded without a recorded
# publisher authorization. robots.txt is not a substitute for content-use terms.
SOURCES = {
    'untourism': dict(name='UN Tourism', base='https://www.untourism.int',
        group='institution', access='public_research_review',
        terms='https://www.untourism.int/copyright',
        note='Local noncommercial research; redistribution/derivative restrictions require review before sharing text.',
        archives=['/news'], paths=['/news/', '/press-release/', '/publications/']),
    'wttc': dict(name='WTTC', base='https://wttc.org', group='association',
        access='public_research_review', terms='https://wttc.org/terms-and-conditions',
        note='Academic research provision; document-specific conditions still apply.',
        archives=['/news', '/blog', '/reports-insights'], paths=['/news/', '/blog/', '/reports/', '/reports-insights/']),
    'ihra': dict(name='IH&RA', base='https://ih-ra.com', group='association',
        access='source_verification_required', terms='',
        note='Supplied domain contains old institutional material mixed with extensive hotel listings. Source identity/current archive unresolved.',
        archives=['/ihra-press-release/'], paths=[]),
    'pata': dict(name='PATA', base='https://www.pata.org', group='association',
        access='publisher_authorization_required', terms='https://www.pata.org/terms-conditions',
        note='Terms restrict automated monitoring/copying without express consent.',
        archives=['/press-releases', '/blog'], paths=['/press-release/', '/blog/', '/member-chapter-news-1/']),
    'ahla': dict(name='AHLA', base='https://www.ahla.com', group='association',
        access='publisher_authorization_required', terms='https://www.ahla.com/ahlacom-terms-use',
        note='Terms restrict scraping/monitoring/copying without express consent.',
        archives=['/news'], paths=['/news/']),
    'etc': dict(name='European Travel Commission', base='https://etc-corporate.org', group='association',
        access='public_research_review', terms='https://etc-corporate.org/privacy-policy/',
        note='Local research only; report-specific copyright notices govern reproduction. No blanket redistribution license established.',
        archives=['/press-centre/', '/publications/'], paths=['/news/', '/reports/']),
    'cto': dict(name='Caribbean Tourism Organization', base='https://www.onecaribbean.org', group='association',
        access='public_research_review', terms='',
        note='Public research collection; no blanket redistribution license established.',
        archives=['/media/cto-news/', '/statistics/annual-reviews-prospects/'], paths=[]),
    'hospitalitynet': dict(name='Hospitality Net', base='https://www.hospitalitynet.org', group='trade_media',
        access='publisher_authorization_required', terms='https://www.hospitalitynet.org/terms-conditions',
        note='Terms restrict bulk extraction; official RSS/API inquiry route: https://www.hospitalitynet.org/rss',
        archives=['/rss'], paths=['/news/', '/opinion/']),
    'travelweekly': dict(name='Travel Weekly', base='https://www.travelweekly.com', group='trade_media',
        access='publisher_authorization_required', terms='https://adhost1.ntmllc.com/twxads/T%26C.htm',
        note='Terms restrict automated access and electronic retention without authorization.',
        archives=['/Travel-News'], paths=['/Travel-News/', '/Articles/']),
}
