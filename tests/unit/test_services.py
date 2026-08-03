import unittest
from radar_concursos.services import infer_organ, slugify

class ServiceTests(unittest.TestCase):
    def test_slugify(self): self.assertEqual(slugify('Técnico Judiciário — TI'),'tecnico-judiciario-ti')
    def test_infer_ifpe(self):
        item=infer_organ('Instituto Federal de Pernambuco','IFPE')
        self.assertEqual(item['sphere'],'Federal'); self.assertEqual(item['scope'],'regional_federal')
    def test_infer_dataprev(self): self.assertEqual(infer_organ('Dataprev','DATAPREV')['scope'],'national')

if __name__=='__main__': unittest.main()
