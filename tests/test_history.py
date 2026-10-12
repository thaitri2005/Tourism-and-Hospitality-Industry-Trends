import unittest
from research.history import parse_page
from research.robots import PublisherRobots


class HistoryTests(unittest.TestCase):
    def test_hospitality_listing_not_an_article(self):
        links, next_url = parse_page('hospitalitynet', 'https://www.hospitalitynet.org/news',
            '<main><a href="/news/123/story">Story</a><a aria-label="Next page" href="/news/page/2">Next</a></main>')
        self.assertEqual(links, ['https://www.hospitalitynet.org/news/123/story'])
        self.assertEqual(next_url, 'https://www.hospitalitynet.org/news/page/2')

    def test_pata_observed_offset(self):
        links, next_url = parse_page('pata', 'https://www.pata.org/blog',
            '<main><a href="/blog/story">Story</a><a rel="next" href="/blog?offset=123">Older Posts</a></main>')
        self.assertEqual(len(links), 1)
        self.assertEqual(next_url, 'https://www.pata.org/blog?offset=123')

    def test_pata_story_text_containing_next_is_not_mistaken_for_pagination(self):
        links, next_url = parse_page('pata', 'https://www.pata.org/press-release',
            '<main><a href="/press-release/pata-gold-award-winners">'
            'PATA Gold Award winners announced next month</a>'
            '<a href="/press-release/other-story">Other story</a></main>')
        self.assertEqual(len(links), 2)
        self.assertIsNone(next_url)

    def test_cto_official_archive_pagination(self):
        links, next_url = parse_page('cto', 'https://www.onecaribbean.org/media/cto-news/',
            '<main><a href="/media/cto-news/climate-action/">Climate action</a>'
            '<a rel="next" href="/media/cto-news/page/2/">Older posts</a></main>')
        self.assertEqual(links, ['https://www.onecaribbean.org/media/cto-news/climate-action/'])
        self.assertEqual(next_url, 'https://www.onecaribbean.org/media/cto-news/page/2/')

    def test_travelweekly_more_articles_query_pagination(self):
        links, next_url = parse_page('travelweekly', 'https://www.travelweekly.com/Travel-News',
            '<main><a href="/Travel-News/Hotel-News/example">Hotel story</a>'
            '<a href="?pg=2">More Articles</a></main>')
        self.assertEqual(links, ['https://www.travelweekly.com/Travel-News/Hotel-News/example'])
        self.assertEqual(next_url, 'https://www.travelweekly.com/Travel-News?pg=2')

    def test_ihra_newsroom_archive_and_out_of_scope_next_link(self):
        links, next_url = parse_page('ihra', 'https://ih-ra.com/newsroom/',
            '<main><a href="/newsroom/industry-update/">Industry update</a>'
            '<a aria-label="Next page" href="/newsroom/page/2/">Next</a></main>')
        self.assertEqual(links, ['https://ih-ra.com/newsroom/industry-update/'])
        self.assertEqual(next_url, 'https://ih-ra.com/newsroom/page/2/')
        with self.assertRaises(ValueError):
            parse_page('ihra', 'https://ih-ra.com/newsroom/',
                       '<main><a href="/newsroom/story/">Story</a>'
                       '<a rel="next" href="/members/page/2/">Next</a></main>')

    def test_empty_or_external_pagination_fails(self):
        with self.assertRaises(ValueError):
            parse_page('ahla', 'https://www.ahla.com/news', '<main>Unavailable</main>')
        with self.assertRaises(ValueError):
            parse_page('ahla', 'https://www.ahla.com/news',
                       '<a href="/news/story">Story</a><a rel="next" href="https://example.org/news">Next</a>')

    def test_wttc_ignoring_page_parameter_fails(self):
        with self.assertRaises(ValueError):
            parse_page('wttc', 'https://wttc.org/news?page=2',
                       '<a href="/news/story">Story</a><input x-ref="searchParams" value=\'{"page":1}\'>')

    def test_robots_wildcards_and_allow_precedence(self):
        robot = PublisherRobots()
        robot.parse(['User-agent: *', 'Disallow: /*?*format=json', 'Disallow: /*.pdf$',
                     'Disallow: /api/', 'Allow: /api/public/', 'Disallow: /same', 'Allow: /same'])
        for path in ['/blog?format=json', '/blog?a=1&format=json', '/report.pdf', '/api/private']:
            self.assertFalse(robot.can_fetch('research', 'https://example.org'+path), path)
        for path in ['/blog?offset=123', '/report.pdf.html', '/api/public/item', '/same']:
            self.assertTrue(robot.can_fetch('research', 'https://example.org'+path), path)


if __name__ == '__main__':
    unittest.main()
