from __future__ import annotations

REQUIRED={"id","organ_id","organ_name","organ_acronym","career","sphere","scope","state","contest_id","contest_title","year","it_category","position","specialty","status","is_official"}
VALID_SCOPES={"regional","regional_federal","national"}
VALID_ERROR_CODES={"OK","NO_RESULTS","SOURCE_NOT_CONFIGURED","MUNICIPALITY_NOT_COVERED","HTTP_ERROR","TIMEOUT","NETWORK_ERROR","INVALID_RESPONSE","PARSER_ERROR","MISSING_OFFICIAL_SOURCE","MANUAL_REVIEW_REQUIRED","PARTIAL_DATA","VACANCY_NOT_FOUND"}

def validate(payload:dict)->list[str]:
    errors=[]
    rows=payload.get("competitions")
    if not isinstance(rows,list):
        return ["O campo competitions precisa ser uma lista."]
    ids=set()
    for index,row in enumerate(rows,start=1):
        missing=REQUIRED-set(row)
        if missing:
            errors.append(f"Registro {index}: campos ausentes: {', '.join(sorted(missing))}")
        rid=str(row.get("id", ""))
        if not rid:
            errors.append(f"Registro {index}: id vazio")
        if rid in ids:
            errors.append(f"Registro {index}: id duplicado: {rid}")
        ids.add(rid)
        if row.get("scope") not in VALID_SCOPES:
            errors.append(f"Registro {index}: scope inválido: {row.get('scope')}")
        for label,status in [("coleta",row.get("collection_status") or {}),("vacância",(row.get("vacancy") or {}).get("collection_status") or {})]:
            if status and status.get("code") not in VALID_ERROR_CODES:
                errors.append(f"Registro {index}: código de {label} inválido: {status.get('code')}")
    return errors
