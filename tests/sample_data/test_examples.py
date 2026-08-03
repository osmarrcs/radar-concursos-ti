import unittest
from radar_concursos.repository import load_dataset

class SampleDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.data=load_dataset()
    def test_ifpe_flow_has_three_contests_and_multiple_positions(self):
        contests=[x for x in self.data['contests']['contests'] if x['organ_id']=='ifpe']
        self.assertGreaterEqual(len(contests),3)
        latest=max(contests,key=lambda x:x['year'])
        positions=[x for x in self.data['positions']['positions'] if x['contest_id']==latest['id']]
        self.assertGreaterEqual(len(positions),6)
    def test_dataprev_is_national(self):
        organ=next(x for x in self.data['organs']['organs'] if x['id']=='dataprev')
        self.assertEqual(organ['scope'],'national')

if __name__=='__main__': unittest.main()
