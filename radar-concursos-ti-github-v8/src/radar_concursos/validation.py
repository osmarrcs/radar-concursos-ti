from __future__ import annotations
from collections.abc import Mapping, Sequence
from datetime import date
from urllib.parse import urlparse
from .status_codes import VALID_STATUS_CODES

VALID_SCOPES = {"regional", "regional_federal", "national"}

def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())

def _url(value: object, *, allow_relative: bool = False) -> bool:
    if not _text(value): return False
    text = str(value).strip()
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"} and bool(parsed.netloc):
        return True
    if allow_relative and not parsed.scheme and not parsed.netloc:
        path = parsed.path.replace("\\", "/")
        return bool(path) and not path.startswith(("/", "../")) and "/../" not in f"/{path}/"
    return False

def _date(value: object, path: str, errors: list[str]) -> None:
    if value in (None, ""): return
    if not isinstance(value, str):
        errors.append(f"{path}: use texto YYYY-MM-DD")
        return
    try: date.fromisoformat(value)
    except ValueError: errors.append(f"{path}: data inválida; use YYYY-MM-DD")

def _sources(value: object, path: str, errors: list[str], *, allow_relative: bool = False) -> None:
    if value in (None, []): return
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        errors.append(f"{path}: precisa ser uma lista")
        return
    for i, item in enumerate(value, 1):
        if not isinstance(item, Mapping):
            errors.append(f"{path}[{i}]: precisa ser objeto")
            continue
        if not _text(item.get("label")): errors.append(f"{path}[{i}].label: obrigatório")
        if not _url(item.get("url"), allow_relative=allow_relative): errors.append(f"{path}[{i}].url: inválida")

def _status(value: object, path: str, errors: list[str]) -> None:
    if value in (None, {}): return
    if not isinstance(value, Mapping):
        errors.append(f"{path}: precisa ser objeto")
        return
    if value.get("code") not in VALID_STATUS_CODES: errors.append(f"{path}.code: inválido")
    if not isinstance(value.get("found"), bool): errors.append(f"{path}.found: precisa ser booleano")
    if not _text(value.get("reason")): errors.append(f"{path}.reason: obrigatório")
    if not _text(value.get("source")): errors.append(f"{path}.source: obrigatório")

def validate_dataset(dataset: Mapping[str, Mapping]) -> list[str]:
    errors: list[str] = []
    organs = dataset.get("organs", {}).get("organs")
    contests = dataset.get("contests", {}).get("contests")
    positions = dataset.get("positions", {}).get("positions")
    alerts = dataset.get("alerts", {})
    updates = dataset.get("updates", {}).get("updates", [])
    if not isinstance(organs, list): errors.append("organs.json: organs precisa ser lista"); organs=[]
    if not isinstance(contests, list): errors.append("contests.json: contests precisa ser lista"); contests=[]
    if not isinstance(positions, list): errors.append("positions.json: positions precisa ser lista"); positions=[]

    organ_ids=set(); contest_ids=set(); position_ids=set()
    for i, organ in enumerate(organs,1):
        p=f"Órgão {i}"
        if not isinstance(organ, Mapping): errors.append(f"{p}: objeto esperado"); continue
        for field in ("id","name","acronym","career","sphere","scope"):
            if not _text(organ.get(field)): errors.append(f"{p}.{field}: obrigatório")
        oid=str(organ.get("id","")).strip()
        if oid in organ_ids: errors.append(f"{p}.id: duplicado {oid}")
        organ_ids.add(oid)
        if organ.get("scope") not in VALID_SCOPES: errors.append(f"{p}.scope: inválido")
        _sources(organ.get("alert_sources"), f"{p}.alert_sources", errors)

    for i, contest in enumerate(contests,1):
        p=f"Concurso {i}"
        if not isinstance(contest, Mapping): errors.append(f"{p}: objeto esperado"); continue
        for field in ("id","organ_id","title","status"):
            if not _text(contest.get(field)): errors.append(f"{p}.{field}: obrigatório")
        cid=str(contest.get("id","")).strip()
        if cid in contest_ids: errors.append(f"{p}.id: duplicado {cid}")
        contest_ids.add(cid)
        if contest.get("organ_id") not in organ_ids: errors.append(f"{p}.organ_id: órgão inexistente")
        year=contest.get("year")
        if not isinstance(year,int) or isinstance(year,bool) or not 1900<=year<=2100: errors.append(f"{p}.year: inválido")
        if not isinstance(contest.get("is_official"),bool): errors.append(f"{p}.is_official: booleano obrigatório")
        _date(contest.get("valid_until"),f"{p}.valid_until",errors)
        _date(contest.get("verified_at"),f"{p}.verified_at",errors)
        _date(contest.get("publication_date"),f"{p}.publication_date",errors)
        _date(contest.get("edital_date"),f"{p}.edital_date",errors)
        _date(contest.get("application_start"),f"{p}.application_start",errors)
        _date(contest.get("application_end"),f"{p}.application_end",errors)
        years=contest.get("validity_years")
        if years is not None and (not isinstance(years,int) or isinstance(years,bool) or years<=0): errors.append(f"{p}.validity_years: inteiro > 0 ou null")
        _sources(contest.get("sources"),f"{p}.sources",errors,allow_relative=True)
        _status(contest.get("collection_status"),f"{p}.collection_status",errors)

    seen_combo=set()
    for i, position in enumerate(positions,1):
        p=f"Cargo {i}"
        if not isinstance(position, Mapping): errors.append(f"{p}: objeto esperado"); continue
        for field in ("id","contest_id","position"):
            if not _text(position.get(field)): errors.append(f"{p}.{field}: obrigatório")
        pid=str(position.get("id","")).strip()
        if pid in position_ids: errors.append(f"{p}.id: duplicado {pid}")
        position_ids.add(pid)
        if position.get("contest_id") not in contest_ids: errors.append(f"{p}.contest_id: concurso inexistente")
        combo=(position.get("contest_id"),str(position.get("position_code","")).strip().casefold(),str(position.get("position","")).strip().casefold(),str(position.get("specialty","")).strip().casefold(),str(position.get("lotation","")).strip().casefold(),str(position.get("quota_type","")).strip().casefold())
        if combo in seen_combo: errors.append(f"{p}: cargo/especialidade/modalidade duplicado no concurso")
        seen_combo.add(combo)
        workload=position.get("workload_hours")
        if workload is not None and (not isinstance(workload,int) or isinstance(workload,bool) or workload<=0): errors.append(f"{p}.workload_hours: inteiro > 0 ou null")
        breakdown=position.get("vacancy_breakdown",{})
        if not isinstance(breakdown,Mapping): errors.append(f"{p}.vacancy_breakdown: objeto esperado")
        else:
            for key,value in breakdown.items():
                if not isinstance(key,str) or not isinstance(value,int) or isinstance(value,bool) or value<0: errors.append(f"{p}.vacancy_breakdown: valores inteiros >= 0")
        for field in ("immediate_vacancies","last_called_rank","total_appointed"):
            value=position.get(field)
            if value is not None and (not isinstance(value,int) or isinstance(value,bool) or value<0): errors.append(f"{p}.{field}: inteiro >= 0 ou null")
        score=position.get("last_called_score")
        if score is not None and (not isinstance(score,(int,float)) or isinstance(score,bool) or score<0): errors.append(f"{p}.last_called_score: número >= 0 ou null")
        _sources(position.get("sources"),f"{p}.sources",errors,allow_relative=True)
        _status(position.get("collection_status"),f"{p}.collection_status",errors)
        vacancy=position.get("vacancy")
        if not isinstance(vacancy,Mapping): errors.append(f"{p}.vacancy: objeto obrigatório")
        else:
            count=vacancy.get("count")
            if count is not None and (not isinstance(count,int) or isinstance(count,bool) or count<0): errors.append(f"{p}.vacancy.count: inteiro >=0 ou null")
            _date(vacancy.get("reference_date"),f"{p}.vacancy.reference_date",errors)
            _sources(vacancy.get("sources"),f"{p}.vacancy.sources",errors,allow_relative=True)
            _status(vacancy.get("collection_status"),f"{p}.vacancy.collection_status",errors)


    if not isinstance(updates,list):
        errors.append("updates.json: updates precisa ser lista")
        updates=[]
    update_ids=set(); update_urls=set()
    for i, update in enumerate(updates,1):
        p=f"Atualização {i}"
        if not isinstance(update,Mapping):
            errors.append(f"{p}: objeto esperado")
            continue
        for field in ("id","organ_id","title","url","event_type","provider"):
            if not _text(update.get(field)): errors.append(f"{p}.{field}: obrigatório")
        uid=str(update.get("id","")).strip()
        if uid in update_ids: errors.append(f"{p}.id: duplicado {uid}")
        update_ids.add(uid)
        if update.get("organ_id") not in organ_ids: errors.append(f"{p}.organ_id: órgão inexistente")
        contest_id=update.get("contest_id","")
        if contest_id and contest_id not in contest_ids: errors.append(f"{p}.contest_id: concurso inexistente")
        if not _url(update.get("url")): errors.append(f"{p}.url: inválida")
        normalized=str(update.get("url","")).strip().casefold()
        if normalized in update_urls: errors.append(f"{p}.url: duplicada")
        update_urls.add(normalized)
        if not isinstance(update.get("official"),bool): errors.append(f"{p}.official: booleano obrigatório")
        if not isinstance(update.get("auto_applied"),bool): errors.append(f"{p}.auto_applied: booleano obrigatório")

    monitored=alerts.get("monitored_organs",[])
    if not isinstance(monitored,list): errors.append("alert_config.monitored_organs: lista obrigatória")
    else:
        for oid in monitored:
            if oid not in organ_ids: errors.append(f"alert_config.monitored_organs: órgão inexistente {oid}")
    providers=alerts.get("providers",{})
    if providers not in ({},None) and not isinstance(providers,Mapping): errors.append("alert_config.providers: objeto esperado")
    search_days=alerts.get("search_days",90)
    if not isinstance(search_days,int) or isinstance(search_days,bool) or not 1<=search_days<=3650:
        errors.append("alert_config.search_days: inteiro entre 1 e 3650")
    if not isinstance(alerts.get("daily_metrics",True),bool): errors.append("alert_config.daily_metrics: booleano obrigatório")
    if not isinstance(alerts.get("notify_errors",True),bool): errors.append("alert_config.notify_errors: booleano obrigatório")
    if not isinstance(alerts.get("notify_open_edicts",True),bool): errors.append("alert_config.notify_open_edicts: booleano obrigatório")
    return errors
