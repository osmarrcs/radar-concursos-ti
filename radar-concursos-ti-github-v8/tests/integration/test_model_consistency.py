import unittest
from radar_concursos.repository import load_dataset

class ConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.data=load_dataset()
    def test_every_contest_has_positions(self):
        refs={x['contest_id'] for x in self.data['positions']['positions']}
        self.assertTrue(all(x['id'] in refs for x in self.data['contests']['contests']))
    def test_every_selected_alert_organ_has_source(self):
        selected=set(self.data['alerts'].get('monitored_organs',[])); organs={x['id']:x for x in self.data['organs']['organs']}
        self.assertTrue(all(organs[x].get('alert_sources') for x in selected))

if __name__=='__main__': unittest.main()
