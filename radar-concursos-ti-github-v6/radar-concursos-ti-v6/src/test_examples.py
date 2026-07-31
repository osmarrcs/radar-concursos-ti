import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'data/competitions.json').read_text(encoding='utf-8'))['competitions']
def contests(org): return sorted({(r['year'],r['contest_id']) for r in data if r['organ_id']==org},reverse=True)
ifpe=contests('ifpe'); dataprev=contests('dataprev')
assert len(ifpe)>=3 and len(dataprev)>=3
ifpe2025=[r for r in data if r['contest_id']=='ifpe-tae-2025']
assert len(ifpe2025)>=6
cats={r['it_category'] for r in ifpe2025}
assert {'Infraestrutura e Segurança','Desenvolvimento e Sistemas','Redes e Infraestrutura','Laboratórios e Suporte'} <= cats
assert all('vacancy' in r for r in data)
print('TEST_RESULT=PASS')
print('IFPE_CONTESTS=',ifpe[:3])
print('IFPE_2025_POSITIONS=',len(ifpe2025))
print('DATAPREV_CONTESTS=',dataprev[:3])
