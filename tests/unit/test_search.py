import unittest

from radar_concursos.search.classifier import classify_event, is_official_url
from radar_concursos.search.orchestrator import SearchOrchestrator
from radar_concursos.search.models import ProviderMetrics, SearchItem
from radar_concursos.search.providers import expand_keywords


class FakeProvider:
    name='fake'
    def search(self, organ, **kwargs):
        items=[
            SearchItem(organ_id=organ['id'],title='UFPE publica edital',url='https://www.ufpe.br/edital.pdf',event_type='edital',provider='fake',official=True,confidence='alta'),
            SearchItem(organ_id=organ['id'],title='Cópia',url='https://www.ufpe.br/edital.pdf?utm_source=x',event_type='edital',provider='fake',official=True,confidence='alta'),
        ]
        return items, ProviderMetrics(provider='fake',attempted=1,succeeded=1,items_scanned=2,relevant_items=2,official_items=2)


class SearchTests(unittest.TestCase):

    def test_free_text_query_is_split_into_terms(self):
        terms=expand_keywords(["concurso edital resultado convocação nomeação vacância"])
        self.assertIn("edital",terms)
        self.assertIn("convocacao",terms)
        self.assertIn("vacancia",terms)

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

    def test_orchestrator_can_search_multiple_organs(self):
        class PerOrganProvider:
            name='fake'
            def search(self, organ, **kwargs):
                item=SearchItem(
                    organ_id=organ['id'],
                    title=f"{organ['acronym']} publica edital",
                    url=f"https://{organ['id']}.gov.br/edital.pdf",
                    event_type='edital', provider='fake', official=True, confidence='alta'
                )
                return [item], ProviderMetrics(provider='fake',attempted=1,succeeded=1,items_scanned=1,relevant_items=1,official_items=1)
        organs=[
            {'id':'ufpe','name':'Universidade Federal de Pernambuco','acronym':'UFPE','alert_sources':[]},
            {'id':'ifpe','name':'Instituto Federal de Pernambuco','acronym':'IFPE','alert_sources':[]},
        ]
        report=SearchOrchestrator([PerOrganProvider()]).search_organs(organs,keywords=['edital'])
        self.assertEqual(report.metrics['organs_searched'],2)
        self.assertEqual(len(report.items),2)
        self.assertEqual({item['organ_id'] for item in report.items},{'ufpe','ifpe'})

if __name__=='__main__': unittest.main()
