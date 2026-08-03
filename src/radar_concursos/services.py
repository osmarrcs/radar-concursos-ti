from __future__ import annotations
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any
from .repository import DATA_DIR, atomic_write_json, load_dataset
from .validation import validate_dataset
from .status_codes import StatusCode

DEFAULT_VACANCY = {
    "count": None,
    "reference_date": "",
    "reason": "Vacância ainda não apurada em fonte oficial específica.",
    "sources": [],
    "collection_status": {"found": False, "code": StatusCode.VACANCY_NOT_FOUND.value, "reason": "Nenhuma fonte de vacância cadastrada.", "source": "vacancia"},
}

def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")

def infer_organ(name: str, acronym: str) -> dict[str, str]:
    text=f"{name} {acronym}".upper()
    result={"career":"Outros órgãos","sphere":"Estadual","scope":"regional","state":"","city":""}
    if any(k in text for k in ("INSTITUTO FEDERAL","UNIVERSIDADE FEDERAL")):
        result.update(career="Universidades e Institutos Federais",sphere="Federal",scope="regional_federal")
    elif any(k in text for k in ("TRF","TRT","TRE","TRIBUNAL REGIONAL")):
        result.update(career="Tribunais",sphere="Federal",scope="regional_federal")
    elif any(k in text for k in ("TJ","TRIBUNAL DE JUSTIÇA")):
        result.update(career="Tribunais",sphere="Estadual",scope="regional")
    elif any(k in text for k in ("DATAPREV","SERPRO","BANCO CENTRAL","TCU","CGU")):
        result.update(career="Órgãos e empresas federais",sphere="Federal",scope="national",state="BR",city="Nacional")
    elif "PREFEITURA" in text or "EMPREL" in text:
        result.update(career="Prefeituras e empresas municipais",sphere="Municipal",scope="regional")
    elif "MINISTÉRIO PÚBLICO" in text or acronym.upper().startswith("MP"):
        result.update(career="Ministérios Públicos",sphere="Estadual",scope="regional")
    return result

def _save_dataset(dataset: dict[str, dict[str, Any]], data_dir: Path) -> None:
    errors=validate_dataset(dataset)
    if errors: raise ValueError("\n".join(errors))
    atomic_write_json(data_dir/"organs.json",dataset["organs"])
    atomic_write_json(data_dir/"contests.json",dataset["contests"])
    atomic_write_json(data_dir/"positions.json",dataset["positions"])
    atomic_write_json(data_dir/"alert_config.json",dataset["alerts"])

def save_organ(name: str, acronym: str, *, overrides: dict[str,str]|None=None, data_dir: Path=DATA_DIR) -> dict[str,Any]:
    if not name.strip() or not acronym.strip(): raise ValueError("Nome e sigla são obrigatórios.")
    dataset=load_dataset(data_dir)
    oid=slugify(acronym)
    inferred=infer_organ(name,acronym)
    inferred.update({k:v for k,v in (overrides or {}).items() if v not in (None,"")})
    record={"id":oid,"name":name.strip(),"acronym":acronym.strip().upper(),**inferred,"alert_sources":[]}
    items=dataset["organs"]["organs"]
    existing=next((i for i,x in enumerate(items) if x["id"]==oid),None)
    if existing is None: items.append(record)
    else:
        record["alert_sources"]=items[existing].get("alert_sources",[])
        items[existing]=record
    _save_dataset(dataset,data_dir)
    return record

def save_contest(record: dict[str,Any], *, data_dir: Path=DATA_DIR) -> dict[str,Any]:
    dataset=load_dataset(data_dir)
    required=("organ_id","title","year","status")
    missing=[x for x in required if record.get(x) in (None,"")]
    if missing: raise ValueError(f"Campos obrigatórios: {', '.join(missing)}")
    cid=record.get("id") or slugify(f"{record['organ_id']}-{record['title']}-{record['year']}")
    clean={
        "id":cid,"organ_id":record["organ_id"],"title":str(record["title"]).strip(),"year":int(record["year"]),
        "status":str(record["status"]).strip(),"valid_until":record.get("valid_until","") or "",
        "reserve_list":record.get("reserve_list"),"lotation":record.get("lotation","") or "",
        "confidence":record.get("confidence","") or "","is_official":bool(record.get("is_official",False)),
        "verified_at":record.get("verified_at") or date.today().isoformat(),"sources":record.get("sources",[]),
        "collection_status":record.get("collection_status",{}),"notes":record.get("notes","") or "",
    }
    items=dataset["contests"]["contests"]
    idx=next((i for i,x in enumerate(items) if x["id"]==cid),None)
    if idx is None: items.append(clean)
    else: items[idx]=clean
    _save_dataset(dataset,data_dir)
    return clean

def save_position(record: dict[str,Any], *, data_dir: Path=DATA_DIR) -> dict[str,Any]:
    dataset=load_dataset(data_dir)
    if not record.get("contest_id") or not str(record.get("position","")).strip(): raise ValueError("Concurso e cargo são obrigatórios.")
    pid=record.get("id") or slugify(f"{record['contest_id']}-{record['position']}-{record.get('specialty','')}-{record.get('quota_type','')}")
    existing=next((x for x in dataset["positions"]["positions"] if x["id"]==pid),None)
    clean={
        "id":pid,"contest_id":record["contest_id"],"position":str(record["position"]).strip(),
        "specialty":str(record.get("specialty","") or "").strip(),"position_code":str(record.get("position_code","") or "").strip(),
        "immediate_vacancies":record.get("immediate_vacancies"),"last_called_rank":record.get("last_called_rank"),
        "last_called_score":record.get("last_called_score"),"total_appointed":record.get("total_appointed"),
        "quota_type":str(record.get("quota_type","") or "").strip(),"sources":record.get("sources",[]),
        "collection_status":record.get("collection_status",{}),"vacancy":copy_vacancy(record.get("vacancy") or (existing or {}).get("vacancy")),
        "notes":str(record.get("notes","") or "").strip(),
    }
    items=dataset["positions"]["positions"]
    idx=next((i for i,x in enumerate(items) if x["id"]==pid),None)
    if idx is None: items.append(clean)
    else: items[idx]=clean
    _save_dataset(dataset,data_dir)
    return clean

def copy_vacancy(value: Any) -> dict[str,Any]:
    if not isinstance(value,dict): return {**DEFAULT_VACANCY,"sources":[],"collection_status":dict(DEFAULT_VACANCY["collection_status"])}
    result={**DEFAULT_VACANCY,**value}
    result["sources"]=list(value.get("sources",[]))
    result["collection_status"]=dict(value.get("collection_status") or DEFAULT_VACANCY["collection_status"])
    return result

def update_vacancy(position_id: str, vacancy: dict[str,Any], *, data_dir: Path=DATA_DIR) -> dict[str,Any]:
    dataset=load_dataset(data_dir)
    position=next((x for x in dataset["positions"]["positions"] if x["id"]==position_id),None)
    if not position: raise ValueError("Cargo não encontrado.")
    position["vacancy"]=copy_vacancy(vacancy)
    _save_dataset(dataset,data_dir)
    return position["vacancy"]


def add_alert_source(organ_id: str, label: str, url: str, source_type: str = "html", *, data_dir: Path=DATA_DIR) -> dict[str,Any]:
    if source_type not in {"html", "rss", "atom", "feed"}:
        raise ValueError("Tipo de fonte inválido. Use html, rss, atom ou feed.")
    if not label.strip() or not url.startswith(("http://", "https://")):
        raise ValueError("Rótulo e URL HTTP(S) são obrigatórios.")
    dataset=load_dataset(data_dir)
    organ=next((x for x in dataset["organs"]["organs"] if x["id"]==organ_id),None)
    if not organ: raise ValueError("Órgão não encontrado.")
    source={"label":label.strip(),"url":url.strip(),"type":source_type}
    sources=organ.setdefault("alert_sources",[])
    index=next((i for i,x in enumerate(sources) if x.get("url")==source["url"]),None)
    if index is None: sources.append(source)
    else: sources[index]=source
    _save_dataset(dataset,data_dir)
    return source

def set_alert_selection(organ_ids: list[str], *, data_dir: Path=DATA_DIR) -> list[str]:
    dataset=load_dataset(data_dir)
    valid={x["id"] for x in dataset["organs"]["organs"]}
    unknown=sorted(set(organ_ids)-valid)
    if unknown: raise ValueError(f"Órgãos inexistentes: {', '.join(unknown)}")
    dataset["alerts"]["monitored_organs"]=sorted(set(organ_ids))
    dataset["alerts"].setdefault("metadata",{})["updated_at"]=date.today().isoformat()
    _save_dataset(dataset,data_dir)
    return dataset["alerts"]["monitored_organs"]
