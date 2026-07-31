#!/usr/bin/env python3
from __future__ import annotations
import json, shutil
from datetime import date
from pathlib import Path
from validate_data import validate
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/competitions.json'; TARGET=ROOT/'docs/data.json'
def main()->None:
    payload=json.loads(SOURCE.read_text(encoding='utf-8'))
    errors=validate(payload)
    if errors: raise SystemExit('\n'.join(errors))
    payload.setdefault('metadata',{})['updated_at']=date.today().isoformat()
    SOURCE.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    shutil.copy2(SOURCE,TARGET)
    contests=len({r['contest_id'] for r in payload['competitions']})
    print(f"Portal atualizado: {len(payload['competitions'])} cargos em {contests} concursos.")
if __name__=='__main__': main()
