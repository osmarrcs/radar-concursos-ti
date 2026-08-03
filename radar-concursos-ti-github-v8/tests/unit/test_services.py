import unittest
from radar_concursos.services import infer_organ, slugify

class ServiceTests(unittest.TestCase):
    def test_slugify(self): self.assertEqual(slugify('Técnico Judiciário — TI'),'tecnico-judiciario-ti')
    def test_infer_ifpe(self):
        item=infer_organ('Instituto Federal de Pernambuco','IFPE')
        self.assertEqual(item['sphere'],'Federal'); self.assertEqual(item['scope'],'regional_federal')
    def test_infer_dataprev(self): self.assertEqual(infer_organ('Dataprev','DATAPREV')['scope'],'national')

if __name__=='__main__': unittest.main()

class SearchUpdateServiceTests(unittest.TestCase):
    def test_search_update_links_latest_contest_and_changes_status(self):
        import json, tempfile
        from pathlib import Path
        from radar_concursos.services import save_search_updates
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'organs.json').write_text(json.dumps({'organs':[{'id':'ufpe','name':'UFPE','acronym':'UFPE','career':'IF','sphere':'Federal','scope':'regional_federal','alert_sources':[]}]}),encoding='utf-8')
            (root/'contests.json').write_text(json.dumps({'contests':[{'id':'ufpe-2026','organ_id':'ufpe','title':'Concurso 2026','year':2026,'status':'Edital publicado','valid_until':'','validity_years':2,'validity_rule':'','publication_date':'2026-08-03','edital_date':'2026-07-29','edital_number':'12','exam_location':'Recife','reserve_list':True,'lotation':'','confidence':'alta','is_official':True,'verified_at':'2026-08-03','sources':[],'collection_status':{},'notes':''}]}),encoding='utf-8')
            (root/'positions.json').write_text(json.dumps({'positions':[]}),encoding='utf-8')
            (root/'updates.json').write_text(json.dumps({'updates':[]}),encoding='utf-8')
            (root/'alert_config.json').write_text(json.dumps({'monitored_organs':[],'search_days':90,'daily_metrics':True}),encoding='utf-8')
            item={'organ_id':'ufpe','title':'UFPE homologa resultado 2026','url':'https://ufpe.br/homologacao','event_type':'homologacao','provider':'fontes_oficiais','source_label':'UFPE','official':True,'confidence':'alta'}
            result=save_search_updates([item],data_dir=root)
            self.assertEqual(result['added_count'],1)
            contests=json.loads((root/'contests.json').read_text())['contests']
            self.assertEqual(contests[0]['status'],'Homologado')
