import copy, unittest
from radar_concursos.repository import load_dataset
from radar_concursos.validation import validate_dataset

class ValidationTests(unittest.TestCase):
    def setUp(self): self.dataset=load_dataset()
    def test_current_dataset_is_valid(self): self.assertEqual(validate_dataset(self.dataset),[])
    def test_rejects_unknown_organ_reference(self):
        data=copy.deepcopy(self.dataset); data['contests']['contests'][0]['organ_id']='missing'
        self.assertTrue(any('órgão inexistente' in x for x in validate_dataset(data)))
    def test_rejects_unknown_contest_reference(self):
        data=copy.deepcopy(self.dataset); data['positions']['positions'][0]['contest_id']='missing'
        self.assertTrue(any('concurso inexistente' in x for x in validate_dataset(data)))
    def test_rejects_duplicate_position_combo(self):
        data=copy.deepcopy(self.dataset); data['positions']['positions'].append(copy.deepcopy(data['positions']['positions'][0])); data['positions']['positions'][-1]['id']='other'
        self.assertTrue(any('duplicado no concurso' in x for x in validate_dataset(data)))

if __name__=='__main__': unittest.main()
