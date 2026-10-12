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
