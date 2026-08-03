import json, tempfile, unittest
from pathlib import Path
from radar_concursos.build import build

class BuildTests(unittest.TestCase):
    def test_build_copies_web_and_writes_normalized_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'dist'; payload=build(dist_dir=out,updated_at='2026-07-31')
            self.assertTrue((out/'index.html').exists()); self.assertTrue((out/'data.json').exists()); self.assertTrue((out/'documents'/'editais').exists())
            loaded=json.loads((out/'data.json').read_text(encoding='utf-8'))
            self.assertEqual(loaded['metadata']['updated_at'],'2026-07-31')
            self.assertEqual(len(payload['positions']),len(loaded['positions']))

if __name__=='__main__': unittest.main()
