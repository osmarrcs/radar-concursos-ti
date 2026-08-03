import json
import tempfile
import unittest
from pathlib import Path

from radar_concursos.alerts.monitor import run
from radar_concursos.search.orchestrator import SearchReport


class FakeOrchestrator:
    def __init__(self, items): self.items=items
    def search_organ(self, organ, **kwargs):
        return SearchReport(
            organ_id=organ['id'], query=organ['acronym'], items=self.items,
            metrics={
                'duration_ms':1,'providers_enabled':1,'provider_attempts':1,'provider_successes':1,
                'provider_failures':0,'items_scanned':len(self.items),'relevant_items':len(self.items),
                'official_items':sum(1 for x in self.items if x.get('official')),'errors':0,'providers':[],
            },
            errors=[], searched_at='2026-08-03T00:00:00+00:00',
        )


class AlertMonitorTests(unittest.TestCase):
    def make_data(self, selected=None):
        tmp=tempfile.TemporaryDirectory(); root=Path(tmp.name)
        (root/'organs.json').write_text(json.dumps({'organs':[{'id':'ifpe','name':'IFPE','acronym':'IFPE','career':'IF','sphere':'Federal','scope':'regional_federal','alert_sources':[]}]}),encoding='utf-8')
        (root/'contests.json').write_text(json.dumps({'contests':[]}),encoding='utf-8')
        (root/'positions.json').write_text(json.dumps({'positions':[]}),encoding='utf-8')
        (root/'updates.json').write_text(json.dumps({'updates':[]}),encoding='utf-8')
        (root/'alert_config.json').write_text(json.dumps({'enabled':True,'monitored_organs':selected or [],'keywords':['edital'],'providers':{'gdelt':True},'search_days':90,'daily_metrics':True,'max_results_per_provider':50,'max_items_per_message':8,'first_run_behavior':'baseline'}),encoding='utf-8')
        (root/'alert_state.json').write_text(json.dumps({'metadata':{'schema_version':'3.0'},'organs':{}}),encoding='utf-8')
        return tmp,root

    def item(self):
        return {'organ_id':'ifpe','title':'Novo edital','url':'https://example.test/edital-1','event_type':'edital','provider':'gdelt','source_label':'example','published_at':'2026-08-03','summary':'','official':False,'confidence':'media','discovered_at':'2026-08-03T00:00:00+00:00'}

    def test_no_selected_organs(self):
        tmp,root=self.make_data([])
        with tmp:
            report=run(data_dir=root,orchestrator=FakeOrchestrator([]))
            self.assertEqual(report['code'],'NO_ORGANS_SELECTED')

    def test_first_run_creates_baseline(self):
        tmp,root=self.make_data(['ifpe'])
        with tmp:
            report=run(data_dir=root,orchestrator=FakeOrchestrator([self.item()]))
            self.assertTrue(report['state_changed'])
            state=json.loads((root/'alert_state.json').read_text())
            self.assertEqual(len(state['organs']['ifpe']),1)

    def test_same_links_do_not_change_state(self):
        tmp,root=self.make_data(['ifpe'])
        with tmp:
            engine=FakeOrchestrator([self.item()])
            run(data_dir=root,orchestrator=engine)
            report=run(data_dir=root,orchestrator=engine)
            self.assertFalse(report['state_changed'])
            self.assertEqual(report['code'],'NO_NEW_ITEMS')

if __name__=='__main__': unittest.main()
