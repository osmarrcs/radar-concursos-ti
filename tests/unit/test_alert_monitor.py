import json
import tempfile
import unittest
from pathlib import Path
from radar_concursos.alerts.monitor import run

class AlertMonitorTests(unittest.TestCase):
    def make_data(self, selected=None):
        tmp=tempfile.TemporaryDirectory(); root=Path(tmp.name)
        (root/'organs.json').write_text(json.dumps({'organs':[{'id':'ifpe','name':'IFPE','acronym':'IFPE','alert_sources':[{'label':'Notícias','url':'https://example.test/news','type':'html'}]}]}),encoding='utf-8')
        (root/'alert_config.json').write_text(json.dumps({'enabled':True,'monitored_organs':selected or [],'keywords':['edital'],'max_items_per_message':8,'first_run_behavior':'baseline'}),encoding='utf-8')
        (root/'alert_state.json').write_text(json.dumps({'metadata':{'schema_version':'2.0'},'sources':{}}),encoding='utf-8')
        return tmp,root
    def test_no_selected_organs(self):
        tmp,root=self.make_data([])
        with tmp:
            report=run(data_dir=root,fetcher=lambda _: '')
            self.assertEqual(report['code'],'NO_ORGANS_SELECTED')
    def test_first_run_creates_baseline(self):
        tmp,root=self.make_data(['ifpe'])
        with tmp:
            report=run(data_dir=root,fetcher=lambda _: '<a href="/edital-1">Novo edital</a>')
            self.assertTrue(report['state_changed'])
            state=json.loads((root/'alert_state.json').read_text())
            self.assertEqual(len(next(iter(state['sources'].values()))),1)
    def test_same_links_do_not_change_state(self):
        tmp,root=self.make_data(['ifpe'])
        with tmp:
            html='<a href="/edital-1">Novo edital</a>'
            run(data_dir=root,fetcher=lambda _: html)
            report=run(data_dir=root,fetcher=lambda _: html)
            self.assertFalse(report['state_changed'])
            self.assertEqual(report['code'],'NO_NEW_ITEMS')

if __name__=='__main__': unittest.main()
