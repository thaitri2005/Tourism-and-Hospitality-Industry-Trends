# Collection notes

Why each website is collected the way it is, and what to check if a source stops working. Checked October 2026.

## Common rules

- The study window is 10 Oct 2016 – 10 Oct 2026 (`research/config.py`). Articles must be English, dated inside the window and
  at least 120 words; reports, event pages, directories and membership pages are excluded.
- Requests to a publisher are sequential, at least 3 s apart, cached, retried with backoff, and logged in `data/corpus.sqlite`
  (`requests` table) and `logs/runs/<run>/events.jsonl`. The user agent identifies the crawler as academic research.
- Wayback Machine requests go one at a time, at least 2 s apart. The Internet Archive refuses connections when a single IP sends
  too fast (seen as `WinError 10061`); the client then backs off for 15–60 s. Two parallel workers were the practical maximum.
- The supervisor reports permission for academic collection of these public pages. No logins, forms, proxies or bot-protection
  work-arounds are used; where a live site refuses automated access, the public web archive is used instead.

## Per website

**UN Tourism.** Sitemaps plus the English `/news?page=N` archive walked back to October 2016 (`backfill.py`). Non-English routes
are excluded by URL.

**WTTC.** The live `/news` and `/blog` archives start in 2019 (the site was rebuilt). Earlier press releases are taken from the
Wayback Machine under two old URL patterns (`/media-centre/press-releases/press-releases/<year>/…` and
`/about/media-centre/…`). These pages carry no date, so the date is the first archive capture when it falls in the year in the
URL, otherwise 1 July of the URL year (flagged `date_year_from_url`, confidence `low`).

**PATA.** Live press releases, blog and member/chapter news from 2020. The pre-2020 site used flat URLs that no longer exist; a
sample of up to 250 archived pages per capture year (2016–2019) is fetched from the Wayback Machine. Undated pages are excluded.

**AHLA.** Live `/news` archive (mostly 2023 onwards) plus archived `/press-release/` pages for earlier years.

**ETC.** Sitemaps, press centre and publications. Report download forms are listed but never submitted.

**CTO (onecaribbean.org).** Every request gets a Sucuri bot-protection 403 page. All archived article URLs (flat slugs) are
fetched from the Wayback Machine. Many CTO items are member-destination press releases republished by CTO; they are kept as
CTO's news output.

**Hospitality Net.** The live archive pages only reach back about three months. Article IDs are sequential (about 4,078,500 in
October 2016 to 4,133,600 in July 2026), and `/news/<id>` redirects to the article, so 1,800 IDs drawn uniformly at random
(seed 20161010) give an unbiased sample of the decade. “External Article” items (excerpts of other publishers' stories,
`/external/` URLs) are excluded in `curate.py`.

**Travel Weekly.** Cloudflare answers every request with a challenge (403). The Wayback Machine index lists about 33,000 archived
`/Travel-News/` articles; up to 170 per capture year (60 for the partial 2016, 140 for 2026) are sampled deterministically.
Roughly 40% of sampled pages fall outside the window or under 120 words and are excluded.

**IH&RA.** ih-ra.com consists of hotel listings and old association pages; the previous site ih-ra.org had a “News” page that
republished Hospitality Net teasers (its article IDs are Hospitality Net IDs). IH&RA therefore has no original content to
analyse in the period. This is reported in the coverage tables instead of substituting another organisation.

## Brand reference list

Global Brands Magazine, *Top 10 Tourism Brands in the World (2026)*: Booking Holdings, Hilton, Marriott International, Airbnb,
Expedia Group, Hyatt, IHG Hotels & Resorts, Disney, Trip.com Group, Accor, with the flagship sub-brands named in the article.
These are the brand groups in `research/codebook.py` (2026 ownership).

## If something changes

- A site redesign usually shows up as `fallback_body_extractor` flags or many `insufficient_text` exclusions for that source in
  `output/tables/exclusions.csv`; add a selector in `extract.py` (re-extraction from saved raw files is automatic).
- To re-sample the archives, change the quotas in `archive.py` (`PLANS`); the discovery checkpoint is keyed to the file, so the
  next run queues only new URLs.
