from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from ..notifications.telegram import send_message
from ..repository import DATA_DIR, atomic_write_json, load_json
from ..search.orchestrator import SearchOrchestrator
from ..services import save_search_updates
from ..status_codes import StatusCode
from .parsers import normalize_url

STATE_PATH=DATA_DIR/"alert_state.json"
LAST_RUN_PATH=DATA_DIR/"alert_last_run.json"


def _metrics_lines(metrics: dict) -> list[str]:
    return [
        f"Órgãos consultados: {metrics.get('organs_checked',0)}",
        f"Provedores: {metrics.get('provider_successes',0)}/{metrics.get('provider_attempts',0)} com sucesso",
        f"Itens analisados: {metrics.get('items_scanned',0)}",
        f"Itens relevantes: {metrics.get('relevant_items',0)}",
        f"Itens oficiais: {metrics.get('official_items',0)}",
        f"Novidades: {metrics.get('new_items',0)}",
        f"Erros: {metrics.get('errors',0)}",
        f"Duração: {metrics.get('duration_ms',0)/1000:.1f}s",
    ]


def format_update_message(organ: dict, items: list[dict], metrics: dict, maximum: int) -> str:
    lines=["🔔 Radar de Concursos",f"Órgão: {organ['acronym']} — {organ['name']}",""]
    for item in items[:maximum]:
        marker="✅" if item.get("official") else "📰"
        kind=str(item.get("event_type","noticia")).replace("_"," ").title()
        lines.extend([f"{marker} {kind}: {item['title']}",item['url'],""])
    if len(items)>maximum:
        lines.append(f"Mais {len(items)-maximum} publicação(ões) não exibida(s).")
    lines.extend(["","📊 Métricas da busca",*_metrics_lines(metrics)])
    return "\n".join(lines).strip()


def format_metrics_message(metrics: dict, details: list[dict]) -> str:
    lines=["📊 Radar de Concursos — resumo da atualização",*_metrics_lines(metrics)]
    failures=[x for x in details if x.get("errors")]
    if failures:
        lines.extend(["",f"Órgãos com erro: {len(failures)}"])
        for item in failures[:5]:
            lines.append(f"• {item.get('organ_id')}: {len(item.get('errors',[]))} erro(s)")
    return "\n".join(lines)


def _enabled_providers(config: dict) -> set[str]:
    providers=config.get("providers") or {"fontes_oficiais":True,"gdelt":True,"querido_diario":True}
    return {name for name,enabled in providers.items() if enabled}


def run(
    *,
    dry_run: bool=False,
    send_metrics: bool=False,
    data_dir: Path=DATA_DIR,
    orchestrator: SearchOrchestrator|None=None,
) -> dict:
    started=time.perf_counter()
    organs_payload=load_json(data_dir/"organs.json")
    config=load_json(data_dir/"alert_config.json")
    state_path=data_dir/"alert_state.json"; last_path=data_dir/"alert_last_run.json"
    state=load_json(state_path) if state_path.exists() else {"metadata":{"schema_version":"3.0"},"organs":{}}
    state.setdefault("organs",{})
    organ_map={x["id"]:x for x in organs_payload["organs"]}
    selected=config.get("monitored_organs",[])
    report={
        "ran_at":datetime.now(timezone.utc).isoformat(),"code":StatusCode.OK.value,
        "reason":"Execução concluída.","state_changed":False,"updates_changed":False,
        "details":[],"metrics":{
            "organs_checked":0,"provider_attempts":0,"provider_successes":0,"provider_failures":0,
            "items_scanned":0,"relevant_items":0,"official_items":0,"new_items":0,"errors":0,"duration_ms":0,
        },
    }
    if not config.get("enabled",True) or not selected:
        report.update(code=StatusCode.NO_ORGANS_SELECTED.value,reason="Nenhum órgão foi selecionado para alertas.")
        report["metrics"]["duration_ms"]=round((time.perf_counter()-started)*1000)
        atomic_write_json(last_path,report); return report

    engine=orchestrator or SearchOrchestrator()
    token=os.getenv("TELEGRAM_BOT_TOKEN",""); chat_id=os.getenv("TELEGRAM_CHAT_ID","")
    baseline=config.get("first_run_behavior","baseline")=="baseline"
    keywords=config.get("keywords",[]); maximum=int(config.get("max_items_per_message",8))
    days=int(config.get("search_days",90)); max_results=int(config.get("max_results_per_provider",50))
    enabled=_enabled_providers(config)
    all_new: list[dict]=[]

    for oid in selected:
        report["metrics"]["organs_checked"]+=1
        organ=organ_map.get(oid)
        if not organ:
            report["details"].append({"organ_id":oid,"errors":[{"code":StatusCode.SOURCE_NOT_CONFIGURED.value,"reason":"Órgão inexistente."}]})
            report["metrics"]["errors"]+=1
            continue
        search_report=engine.search_organ(organ,keywords=keywords,days=days,max_results=max_results,enabled_providers=enabled)
        m=search_report.metrics
        for key in ("provider_attempts","provider_successes","provider_failures","items_scanned","relevant_items","official_items","errors"):
            report["metrics"][key]+=int(m.get(key,0))
        current={normalize_url(x["url"]):x for x in search_report.items}
        known=set(state["organs"].get(oid,[]))
        if not known and baseline:
            state["organs"][oid]=sorted(current)
            report["state_changed"]=bool(current)
            report["details"].append({"organ_id":oid,"code":StatusCode.BASELINE_CREATED.value,"found":len(current),"errors":search_report.errors,"metrics":m})
            continue
        new=[item for url,item in current.items() if url not in known]
        if not config.get("notify_open_edicts", True):
            new=[item for item in new if item.get("event_type") != "edital"]
        report["metrics"]["new_items"]+=len(new)
        sent=False
        if new:
            if dry_run:
                print(format_update_message(organ,new,m,maximum)); sent=True
            elif not token or not chat_id:
                report["details"].append({"organ_id":oid,"code":StatusCode.TELEGRAM_NOT_CONFIGURED.value,"found":len(new),"errors":search_report.errors,"metrics":m})
            else:
                result=send_message(token,chat_id,format_update_message(organ,new,m,maximum))
                sent=result.ok
                report["details"].append({"organ_id":oid,"code":result.code,"reason":result.reason,"found":len(new),"errors":search_report.errors,"metrics":m})
            if sent:
                all_new.extend(new)
                state["organs"][oid]=sorted(set(known)|set(current))
                report["state_changed"]=True
        else:
            report["details"].append({"organ_id":oid,"code":StatusCode.NO_NEW_ITEMS.value,"found":0,"errors":search_report.errors,"metrics":m})
            # Atualiza a linha de base somente com URLs atualmente conhecidas sem alterar a semântica de novidades.
            merged=sorted(set(known)|set(current))
            if merged!=state["organs"].get(oid,[]):
                state["organs"][oid]=merged; report["state_changed"]=True

    if all_new and not dry_run:
        saved=save_search_updates(all_new,auto_apply=True,data_dir=data_dir)
        report["updates_changed"]=saved["added_count"]>0
        report["saved_updates"]=saved

    report["metrics"]["duration_ms"]=round((time.perf_counter()-started)*1000)
    if report["metrics"]["new_items"]==0:
        report.update(code=StatusCode.NO_NEW_ITEMS.value,reason="Nenhuma publicação nova encontrada.")
    if config.get("notify_errors", True) and report["metrics"].get("errors", 0) and not send_metrics:
        send_metrics = True
    if send_metrics and not dry_run:
        if token and chat_id:
            result=send_message(token,chat_id,format_metrics_message(report["metrics"],report["details"]))
            report["metrics_message"]={"code":result.code,"reason":result.reason,"ok":result.ok}
        else:
            report["metrics_message"]={"code":StatusCode.TELEGRAM_NOT_CONFIGURED.value,"reason":"Configure os Secrets do Telegram.","ok":False}
    elif send_metrics and dry_run:
        print(format_metrics_message(report["metrics"],report["details"]))

    if report["state_changed"] and not dry_run:
        state.setdefault("metadata",{})["schema_version"]="3.0"
        state["metadata"]["updated_at"]=datetime.now(timezone.utc).isoformat()
        atomic_write_json(state_path,state)
    atomic_write_json(last_path,report)
    return report


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("--send-metrics",action="store_true")
    args=parser.parse_args()
    report=run(dry_run=args.dry_run,send_metrics=args.send_metrics)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
