import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

class NotebookTests(unittest.TestCase):
    def test_notebook_has_single_executable_bootstrap_cell(self):
        notebook=json.loads((ROOT/'Radar_Concursos_TI_Colab.ipynb').read_text(encoding='utf-8'))
        code=[cell for cell in notebook['cells'] if cell['cell_type']=='code']
        self.assertEqual(len(code),1)
        source=''.join(code[0]['source'])
        self.assertIn('radar_concursos.colab_app',source)
        self.assertIn('git", "clone',source)

if __name__=='__main__': unittest.main()
