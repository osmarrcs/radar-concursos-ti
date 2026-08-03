import unittest
from radar_concursos.alerts.parsers import deduplicate, normalize_url, parse_feed, parse_html

class AlertParserTests(unittest.TestCase):
    def test_removes_tracking(self):
        self.assertEqual(normalize_url('HTTPS://EXAMPLE.COM/a/?utm_source=x&x=1#t'),'https://example.com/a?x=1')
    def test_html_parser(self):
        items=parse_html('<a href="/edital?utm_campaign=x">Novo edital</a>','https://example.com/noticias/')
        self.assertEqual(items[0]['url'],'https://example.com/edital')
    def test_feed_parser(self):
        xml='<rss><channel><item><title>Edital 1</title><link>https://e.test/a</link></item></channel></rss>'
        self.assertEqual(parse_feed(xml,'https://e.test')[0]['title'],'Edital 1')
    def test_deduplicate(self): self.assertEqual(len(deduplicate([{'title':'A','url':'https://e.test/a?utm_source=x'},{'title':'B','url':'https://e.test/a'}])),1)

if __name__=='__main__': unittest.main()
