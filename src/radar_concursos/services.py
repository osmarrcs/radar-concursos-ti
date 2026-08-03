from __future__ import annotations
import re
import unicodedata
import hashlib
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from .repository import DATA_DIR, atomic_write_json, load_dataset
from .validation import validate_dataset
from .status_codes import StatusCode
from .alerts.parsers import normalize_url
from .search.classifier import priority_for_event, status_for_event

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
    if any(k in text for k in ("POLÍCIA FEDERAL", "POLICIA FEDERAL", "POLÍCIA RODOVIÁRIA FEDERAL", "POLICIA RODOVIARIA FEDERAL", "ABIN", "AGÊNCIA BRASILEIRA DE INTELIGÊNCIA", "AGENCIA BRASILEIRA DE INTELIGENCIA")):
        result.update(career="Carreiras Policiais e Inteligência",sphere="Federal",scope="national",state="BR",city="Nacional")
    elif any(k in text for k in ("INSTITUTO FEDERAL","UNIVERSIDADE FEDERAL")):
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
    atomic_write_json(data_dir/"updates.json",dataset["updates"])

def save_organ(name: str, acronym: str, *, overrides: dict[str,str]|None=None, data_dir: Path=DATA_DIR) -> dict[str,Any]:
    if not name.strip() or not acronym.strip(): raise ValueError("Nome e sigla são obrigatórios.")
    dataset=load_dataset(data_dir)
    oid=slugify(acronym)
    inferred=infer_organ(name,acronym)
    inferred.update({k:v for k,v in (overrides or {}).items() if v not in (None,"")})
    record={"id":oid,"name":name.strip(),"acronym":acronym.strip().upper(),**inferred,"alert_sources":[]}
    items=dataset["organs"]["organs"]
    existing=next((i for i,x in enumerate(items) if x["id"]==oid),None)
    if existing is None:
        record.setdefault("official_domains",[])
        record.setdefault("territory_id","")
        items.append(record)
    else:
        previous=items[existing]
        record["alert_sources"]=previous.get("alert_sources",[])
        record["official_domains"]=(overrides or {}).get("official_domains",previous.get("official_domains",[]))
        record["territory_id"]=(overrides or {}).get("territory_id",previous.get("territory_id",""))
        for key in ("state","city","career","sphere","scope"):
            if not record.get(key) and previous.get(key): record[key]=previous[key]
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
        "validity_years":record.get("validity_years"),"validity_rule":record.get("validity_rule","") or "",
        "publication_date":record.get("publication_date","") or "","edital_date":record.get("edital_date","") or "",
        "application_start":record.get("application_start","") or "","application_end":record.get("application_end","") or "",
        "edital_number":str(record.get("edital_number","") or "").strip(),
        "exam_location":str(record.get("exam_location","") or "").strip(),
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
    pid=record.get("id") or slugify(f"{record['contest_id']}-{record.get('position_code','')}-{record['position']}-{record.get('specialty','')}-{record.get('lotation','')}-{record.get('quota_type','')}")
    existing=next((x for x in dataset["positions"]["positions"] if x["id"]==pid),None)
    clean={
        "id":pid,"contest_id":record["contest_id"],"position":str(record["position"]).strip(),
        "specialty":str(record.get("specialty","") or "").strip(),"position_code":str(record.get("position_code","") or "").strip(),
        "workload_hours":record.get("workload_hours"),"level":str(record.get("level","") or "").strip(),
        "lotation":str(record.get("lotation","") or "").strip(),"vacancy_breakdown":record.get("vacancy_breakdown",{}),
        "immediate_vacancies":record.get("immediate_vacancies"),"last_called_name":str(record.get("last_called_name","") or "").strip(),
        "last_called_rank":record.get("last_called_rank"),"last_called_score":record.get("last_called_score"),"total_appointed":record.get("total_appointed"),
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
    host=urlsplit(source["url"]).netloc.casefold().removeprefix("www.")
    domains=organ.setdefault("official_domains",[])
    if host and host not in domains: domains.append(host)
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

def update_call_history(position_id: str, history: dict[str, Any], *, data_dir: Path=DATA_DIR) -> dict[str, Any]:
    dataset=load_dataset(data_dir)
    position=next((x for x in dataset["positions"]["positions"] if x["id"]==position_id),None)
    if not position: raise ValueError("Cargo não encontrado.")
    for field in ("last_called_rank","total_appointed"):
        value=history.get(field)
        if value is not None and (not isinstance(value,int) or isinstance(value,bool) or value<0):
            raise ValueError(f"{field} deve ser inteiro maior ou igual a zero.")
    score=history.get("last_called_score")
    if score is not None and (not isinstance(score,(int,float)) or isinstance(score,bool) or score<0):
        raise ValueError("last_called_score deve ser número maior ou igual a zero.")
    position["last_called_name"]=str(history.get("last_called_name") or "").strip()
    position["last_called_rank"]=history.get("last_called_rank")
    position["last_called_score"]=history.get("last_called_score")
    position["total_appointed"]=history.get("total_appointed")
    if history.get("quota_type") not in (None,""):
        position["quota_type"]=str(history["quota_type"]).strip()
    if history.get("sources") is not None:
        position["sources"]=list(history.get("sources") or [])
    if history.get("collection_status") is not None:
        position["collection_status"]=dict(history.get("collection_status") or {})
    if history.get("notes") not in (None,""):
        position["notes"]=str(history["notes"]).strip()
    _save_dataset(dataset,data_dir)
    return position


def _detect_year(value: str) -> int | None:
    matches=re.findall(r"\b(20\d{2})\b",value or "")
    return int(matches[0]) if matches else None


def _match_contest(dataset: dict[str, dict[str, Any]], organ_id: str, item: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    contests=[x for x in dataset["contests"]["contests"] if x.get("organ_id")==organ_id]
    if not contests:
        return None, False
    explicit=item.get("contest_id")
    if explicit:
        matched=next((x for x in contests if x.get("id")==explicit),None)
        if matched:
            return matched, True
    year=_detect_year(f"{item.get('title','')} {item.get('published_at','')}")
    if year:
        candidates=[x for x in contests if x.get("year")==year]
        if candidates:
            return sorted(candidates,key=lambda x:(x.get("publication_date",''),x.get("verified_at",'')),reverse=True)[0], True
    ordered=sorted(contests,key=lambda x:(x.get("year",0),x.get("publication_date",''),x.get("verified_at",'')),reverse=True)
    return ordered[0], len(ordered)==1


def save_search_updates(
    items: list[dict[str, Any]],
    *,
    auto_apply: bool=True,
    data_dir: Path=DATA_DIR,
) -> dict[str, Any]:
    """Persist search results and optionally refresh the latest matching contest.

    Automatic application is conservative: the update is linked to a contest from the
    same organ, preferring an explicit year in the title. Status changes are only made
    for official results and only when the event has equal or greater progression.
    """
    dataset=load_dataset(data_dir)
    updates=dataset["updates"].setdefault("updates",[])
    known={normalize_url(x.get("url","")):x for x in updates if x.get("url")}
    added=[]; linked=0; status_changes=[]
    for raw in items:
        url=normalize_url(str(raw.get("url","")).strip())
        organ_id=str(raw.get("organ_id","")).strip()
        if not url or not organ_id:
            continue
        if url in known:
            continue
        uid="upd-"+hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        item={
            "id":uid,
            "organ_id":organ_id,
            "contest_id":"",
            "title":str(raw.get("title") or url).strip(),
            "url":url,
            "published_at":str(raw.get("published_at") or "").strip(),
            "event_type":str(raw.get("event_type") or "noticia").strip(),
            "provider":str(raw.get("provider") or "manual").strip(),
            "source_label":str(raw.get("source_label") or "").strip(),
            "summary":str(raw.get("summary") or "").strip()[:2000],
            "official":bool(raw.get("official",False)),
            "confidence":str(raw.get("confidence") or "media").strip(),
            "discovered_at":str(raw.get("discovered_at") or datetime.now(timezone.utc).isoformat()),
            "auto_applied":False,
        }
        contest, confident_match=_match_contest(dataset,organ_id,item)
        if contest:
            item["contest_id"]=contest["id"]
            linked+=1
            if auto_apply and item["official"] and confident_match:
                source={"label":item["source_label"] or item["title"],"url":item["url"]}
                sources=contest.setdefault("sources",[])
                if not any(normalize_url(x.get("url",""))==item["url"] for x in sources):
                    sources.append(source)
                current_event=str(contest.get("last_event_type") or "noticia")
                if priority_for_event(item["event_type"])>=priority_for_event(current_event):
                    before=contest.get("status","")
                    after=status_for_event(item["event_type"])
                    contest["status"]=after
                    contest["last_event_type"]=item["event_type"]
                    contest["verified_at"]=date.today().isoformat()
                    contest["collection_status"]={
                        "found":True,
                        "code":StatusCode.OK.value,
                        "reason":"Status atualizado automaticamente a partir de publicação oficial; confirme no link vinculado.",
                        "source":item["provider"],
                    }
                    item["auto_applied"]=True
                    if before!=after:
                        status_changes.append({"contest_id":contest["id"],"before":before,"after":after,"update_id":uid})
        updates.append(item); known[url]=item; added.append(item)
    if added:
        dataset["updates"].setdefault("metadata",{})["updated_at"]=datetime.now(timezone.utc).isoformat()
        _save_dataset(dataset,data_dir)
    return {"added":added,"added_count":len(added),"linked_count":linked,"status_changes":status_changes}


def update_alert_preferences(
    *,
    organ_ids: list[str] | None=None,
    keywords: list[str] | None=None,
    providers: dict[str,bool] | None=None,
    search_days: int | None=None,
    daily_metrics: bool | None=None,
    notify_errors: bool | None=None,
    notify_open_edicts: bool | None=None,
    data_dir: Path=DATA_DIR,
) -> dict[str, Any]:
    dataset=load_dataset(data_dir)
    config=dataset["alerts"]
    valid={x["id"] for x in dataset["organs"]["organs"]}
    if organ_ids is not None:
        unknown=sorted(set(organ_ids)-valid)
        if unknown:
            raise ValueError(f"Órgãos inexistentes: {', '.join(unknown)}")
        config["monitored_organs"]=sorted(set(organ_ids))
    if keywords is not None:
        clean=[x.strip() for x in keywords if x and x.strip()]
        if not clean:
            raise ValueError("Informe ao menos uma palavra-chave.")
        config["keywords"]=list(dict.fromkeys(clean))
    if providers is not None:
        config["providers"]={
            "fontes_oficiais":bool(providers.get("fontes_oficiais",True)),
            "gdelt":bool(providers.get("gdelt",True)),
            "querido_diario":bool(providers.get("querido_diario",True)),
        }
    if search_days is not None:
        if not 1<=int(search_days)<=3650:
            raise ValueError("search_days deve ficar entre 1 e 3650.")
        config["search_days"]=int(search_days)
    if daily_metrics is not None:
        config["daily_metrics"]=bool(daily_metrics)
    if notify_errors is not None:
        config["notify_errors"]=bool(notify_errors)
    if notify_open_edicts is not None:
        config["notify_open_edicts"]=bool(notify_open_edicts)
    config.setdefault("metadata",{})["updated_at"]=date.today().isoformat()
    _save_dataset(dataset,data_dir)
    return config
