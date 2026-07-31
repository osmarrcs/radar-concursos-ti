#!/usr/bin/env python3
"""Valida a base JSON e copia os dados para o diretório publicado no GitHub Pages."""
from __future__ import annotations
import json
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "competitions.json"
TARGET = ROOT / "docs" / "data.json"
REQUIRED = {"id","organ_id","organ_name","organ_acronym","career","sphere","scope","state","year","position","specialty","status","is_official"}
VALID_SCOPES = {"regional", "regional_federal", "national"}

def validate(payload: dict) -> list[str]:
    errors: list[str] = []
    rows = payload.get("competitions")
    if not isinstance(rows, list):
        return ["O campo competitions precisa ser uma lista."]
    ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        missing = REQUIRED - set(row)
        if missing:
            errors.append(f"Registro {index}: campos ausentes: {', '.join(sorted(missing))}")
        row_id = str(row.get("id", ""))
        if row_id in ids:
            errors.append(f"Registro {index}: id duplicado: {row_id}")
        ids.add(row_id)
        if row.get("scope") not in VALID_SCOPES:
            errors.append(f"Registro {index}: scope inválido: {row.get('scope')}")
        score = row.get("predictability_score", 0)
        if not isinstance(score, (int, float)) or not 0 <= score <= 100:
            errors.append(f"Registro {index}: predictability_score deve estar entre 0 e 100")
    return errors

def main() -> None:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    errors = validate(payload)
    if errors:
        raise SystemExit("\n".join(errors))
    payload.setdefault("metadata", {})["updated_at"] = date.today().isoformat()
    SOURCE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(SOURCE, TARGET)
    print(f"Site atualizado: {len(payload['competitions'])} registros copiados para {TARGET.relative_to(ROOT)}")

if __name__ == "__main__":
    main()
