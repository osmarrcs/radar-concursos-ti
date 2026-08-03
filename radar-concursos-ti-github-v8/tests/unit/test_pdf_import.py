import unittest
from pathlib import Path
from radar_concursos.pdf_import import parse_edital_metadata, parse_positions_from_text

FIXTURE=Path(__file__).resolve().parents[1]/'fixtures'/'edital_sample.txt'

class PdfImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.text=FIXTURE.read_text(encoding='utf-8')
    def test_metadata(self):
        item=parse_edital_metadata(self.text,'ufpe.pdf')
        self.assertEqual(item['edital_number'],'12')
        self.assertEqual(item['publication_date'],'2026-08-03')
        self.assertEqual(item['validity_years'],2)
        self.assertEqual(item['exam_location'],'Região Metropolitana de Recife-PE')
    def test_parses_all_rows_without_it_filter(self):
        rows=parse_positions_from_text(self.text)
        self.assertEqual(len(rows),4)
        self.assertIn('Assistente em administração',[x['position'] for x in rows])
    def test_multiline_it_rows(self):
        rows={x['position_code']:x for x in parse_positions_from_text(self.text)}
        self.assertEqual(rows['4']['specialty'],'Desenvolvimento de Sistemas')
        self.assertEqual(rows['6']['specialty'],'Suporte a Centro de Dados e Redes')
        self.assertEqual(rows['12']['specialty'],'Datacenter e Redes')
        self.assertEqual(rows['37']['lotation'],'Sertânia')

if __name__=='__main__': unittest.main()
