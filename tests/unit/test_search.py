import unittest

from radar_concursos.search.classifier import classify_event, is_official_url
from radar_concursos.search.orchestrator import SearchOrchestrator
from radar_concursos.search.models import ProviderMetrics, SearchItem


class FakeProvider:
    name='fake'
    def search(self, organ, **kwargs):
        items=[
            SearchItem(organ_id=organ['id'],title='UFPE publica edital',url='https://www.ufpe.br/edital.pdf',event_type='edital',provider='fake',official=True,confidence='alta'),
            SearchItem(organ_id=organ['id'],title='Cópia',url='https://www.ufpe.br/edital.pdf?utm_source=x',event_type='edital',provider='fake',official=True,confidence='alta'),
        ]
        return items, ProviderMetrics(provider='fake',attempted=1,succeeded=1,items_scanned=2,relevant_items=2,official_items=2)


class SearchTests(unittest.TestCase):
    def test_classifier(self):
        self.assertEqual(classify_event('Resultado final homologado do concurso'),'homologacao')
        self.assertEqual(classify_event('Portaria de nomeação dos aprovados'),'nomeacao')

    def test_official_domain(self):
        self.assertTrue(is_official_url('https://portal.ifpe.edu.br/noticia'))
        self.assertFalse(is_official_url('https://example.com/noticia'))

    def test_orchestrator_deduplicates_and_reports_metrics(self):
        organ={'id':'ufpe','name':'Universidade Federal de Pernambuco','acronym':'UFPE','alert_sources':[]}
        report=SearchOrchestrator([FakeProvider()]).search_organ(organ,keywords=['edital'])
        self.assertEqual(len(report.items),1)
        self.assertEqual(report.metrics['items_scanned'],2)
        self.assertEqual(report.metrics['relevant_items'],1)
        self.assertEqual(report.metrics['provider_successes'],1)

if __name__=='__main__': unittest.main()
