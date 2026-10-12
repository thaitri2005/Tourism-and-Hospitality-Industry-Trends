from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OUTPUT = ROOT / 'output'
START = '2016-10-10'
END = '2026-10-10'
USER_AGENT = 'TourismResearchPilot/0.1 (academic research; public content only)'

# Source scope is user-directed. Runtime checks honor parseable robots.txt rules,
# HTTP content denials, rate limits, and host restrictions. A per-source 403-on-
# robots fallback is available only where configured below. For CTO and Travel
# Weekly, the user reports explicit permission that supersedes robots directives
# for this research. A 403 on one URL is recorded and skipped while other public
# URLs are attempted slowly. No authentication, stealth, proxy, or rate-limit
# evasion is used.
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
        access='public_research_review', terms='', retry_blocked_once=True,
        note='User-directed public-page research attempt; target official press-release, industry-news, and newsroom archives. Site history is sparse/dated; confirm association attribution and study-window coverage.',
        archives=['/ihra-press-release/', '/industry-news/members-press-release/',
                  '/news/members-press-release', '/newsroom/'],
        paths=['/ihra-press-release/', '/industry-news/', '/news/', '/newsroom/']),
    'pata': dict(name='PATA', base='https://www.pata.org', group='association',
        access='public_research_review', terms='https://www.pata.org/terms-conditions', retry_blocked_once=True,
        note='User-directed public-page research attempt. PATA terms state automated monitoring/copying requires prior express consent; review retention and reuse before sharing.',
        archives=['/press-releases', '/blog'], paths=['/press-release/', '/blog/', '/member-chapter-news-1/']),
    'ahla': dict(name='AHLA', base='https://www.ahla.com', group='association',
        access='public_research_review', terms='https://www.ahla.com/ahlacom-terms-use', retry_blocked_once=True,
        note='User-directed public-page research attempt. AHLA terms state automated scraping/monitoring/copying requires prior express consent; review retention and reuse before sharing.',
        archives=['/news'], paths=['/news/']),
    'etc': dict(name='European Travel Commission', base='https://etc-corporate.org', group='association',
        access='public_research_review', terms='https://etc-corporate.org/privacy-policy/',
        note='Local research only; report-specific copyright notices govern reproduction. No blanket redistribution license established.',
        archives=['/press-centre/', '/publications/'], paths=['/news/', '/reports/']),
    'cto': dict(name='Caribbean Tourism Organization', base='https://www.onecaribbean.org', group='association',
        access='public_research_review', terms='',
        note='User reports authorization for publicly accessible academic research. A robots.txt 403 is treated as unavailable under RFC 9309; each content URL returning 403 is recorded and skipped while other configured public pages are attempted slowly. No blanket redistribution license established.',
        allow_robots_403_unavailable=True,
        ignore_robots=True,
        continue_after_url_403=True,
        retry_blocked_once=True, archives=['/media/cto-news/', '/statistics/annual-reviews-prospects/'],
        paths=['/media/cto-news/', '/statistics/annual-reviews-prospects/']),
    'hospitalitynet': dict(name='Hospitality Net', base='https://www.hospitalitynet.org', group='trade_media',
        access='public_research_review', terms='https://www.hospitalitynet.org/terms-conditions', retry_blocked_once=True,
        note='User-directed public-page research attempt. Official RSS feed used as a discovery route; review retention and reuse terms before sharing.',
        archives=['/rss'], paths=['/news/', '/opinion/']),
    'travelweekly': dict(name='Travel Weekly', base='https://www.travelweekly.com', group='trade_media',
        access='public_research_review', terms='https://adhost1.ntmllc.com/twxads/T%26C.htm', retry_blocked_once=True,
        allow_robots_403_unavailable=True,
        ignore_robots=True,
        continue_after_url_403=True,
        note='User reports authorization for publicly accessible academic research. A robots.txt 403 is treated as unavailable under RFC 9309; each content URL returning 403 is recorded and skipped while other configured public pages are attempted slowly. Review retention and reuse terms before sharing.',
        archives=['/Travel-News'], paths=['/Travel-News/', '/Articles/']),
}
