from __future__ import annotations
import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any
from .repository import ROOT, load_dataset
from .validation import validate_dataset

WEB_DIR=ROOT/"web"
DIST_DIR=ROOT/"dist"

def prepare_payload(dataset: dict[str,dict[str,Any]], updated_at: str|None=None) -> dict[str,Any]:
    errors=validate_dataset(dataset)
    if errors: raise ValueError("\n".join(errors))
    return {
        "metadata":{"schema_version":"2.0","updated_at":updated_at or date.today().isoformat()},
        "organs":dataset["organs"]["organs"],
        "contests":dataset["contests"]["contests"],
        "positions":dataset["positions"]["positions"],
    }

def build(web_dir: Path=WEB_DIR, dist_dir: Path=DIST_DIR, updated_at: str|None=None) -> dict[str,Any]:
    payload=prepare_payload(load_dataset(),updated_at)
    if dist_dir.exists(): shutil.rmtree(dist_dir)
    shutil.copytree(web_dir,dist_dir)
    (dist_dir/"data.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return payload

def main() -> None:
    try: payload=build()
    except (OSError,ValueError) as exc: raise SystemExit(str(exc)) from exc
    print(f"Portal gerado: {len(payload['organs'])} órgãos, {len(payload['contests'])} concursos e {len(payload['positions'])} cargos.")

if __name__=="__main__": main()
