from __future__ import annotations
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from ..repository import DATA_DIR, atomic_write_json, load_json
from ..notifications.telegram import send_message
from .parsers import deduplicate, parse_feed, parse_html
from ..status_codes import StatusCode

STATE_PATH=DATA_DIR/"alert_state.json"
LAST_RUN_PATH=DATA_DIR/"alert_last_run.json"

def fetch(url: str, timeout: int=25) -> str:
    request=Request(url,headers={"User-Agent":"radar-concursos-ti/0.9 (+GitHub Actions)"})
    with urlopen(request,timeout=timeout) as response: return response.read().decode("utf-8",errors="replace")

def matches(item: dict[str,str], keywords: list[str]) -> bool:
    haystack=f"{item.get('title','')} {item.get('url','')}".casefold()
    return any(word.casefold() in haystack for word in keywords)

def source_key(organ_id: str, source_url: str) -> str: return f"{organ_id}|{source_url}"

def format_message(organ: dict, items: list[dict[str,str]], maximum: int) -> str:
    lines=["🔔 Radar de Concursos",f"Órgão: {organ['acronym']} — {organ['name']}",""]
    for item in items[:maximum]: lines.extend([f"• {item['title']}",item['url'],""])
    if len(items)>maximum: lines.append(f"Mais {len(items)-maximum} publicação(ões) não exibida(s).")
    return "\n".join(lines).strip()

def run(*,dry_run: bool=False, fetcher=fetch, data_dir: Path=DATA_DIR) -> dict:
    organs_payload=load_json(data_dir/"organs.json")
    config=load_json(data_dir/"alert_config.json")
    state_path=data_dir/"alert_state.json"; last_path=data_dir/"alert_last_run.json"
    state=load_json(state_path) if state_path.exists() else {"metadata":{"schema_version":"2.0"},"sources":{}}
    organ_map={x["id"]:x for x in organs_payload["organs"]}
    selected=config.get("monitored_organs",[])
    report={"ran_at":datetime.now(timezone.utc).isoformat(),"code":StatusCode.OK.value,"reason":"Execução concluída.","organs_checked":0,"sources_checked":0,"new_items":0,"state_changed":False,"details":[]}
    if not config.get("enabled",True) or not selected:
        report.update(code=StatusCode.NO_ORGANS_SELECTED.value,reason="Nenhum órgão foi selecionado para alertas.")
        atomic_write_json(last_path,report); return report
    keywords=config.get("keywords",[]); maximum=int(config.get("max_items_per_message",8)); baseline=config.get("first_run_behavior","baseline")=="baseline"
    token=os.getenv("TELEGRAM_BOT_TOKEN",""); chat_id=os.getenv("TELEGRAM_CHAT_ID","")
    for oid in selected:
        organ=organ_map.get(oid); report["organs_checked"]+=1
        if not organ: report["details"].append({"organ_id":oid,"code":StatusCode.SOURCE_NOT_CONFIGURED.value,"reason":"Órgão inexistente."}); continue
        sources=organ.get("alert_sources",[])
        if not sources: report["details"].append({"organ_id":oid,"code":StatusCode.SOURCE_NOT_CONFIGURED.value,"reason":"Nenhuma fonte oficial configurada."}); continue
        organ_new=[]; staged={}
        for source in sources:
            report["sources_checked"]+=1; key=source_key(oid,source["url"])
            try:
                content=fetcher(source["url"])
                items=parse_feed(content,source["url"]) if source.get("type") in {"rss","atom","feed"} else parse_html(content,source["url"])
                items=deduplicate([x for x in items if matches(x,keywords)])
            except HTTPError as exc:
                report["details"].append({"organ_id":oid,"code":StatusCode.HTTP_ERROR.value,"reason":f"HTTP {exc.code}","source":source["url"]}); continue
            except (URLError,TimeoutError) as exc:
                report["details"].append({"organ_id":oid,"code":StatusCode.NETWORK_ERROR.value,"reason":str(exc),"source":source["url"]}); continue
            except Exception as exc:
                report["details"].append({"organ_id":oid,"code":StatusCode.PARSER_ERROR.value,"reason":str(exc),"source":source["url"]}); continue
            known=set(state.get("sources",{}).get(key,[])); current=[x["url"] for x in items]
            if not known and baseline:
                staged[key]=current
                if current != state.get("sources",{}).get(key,[]): report["state_changed"]=True
                report["details"].append({"organ_id":oid,"code":StatusCode.BASELINE_CREATED.value,"reason":f"Linha de base com {len(current)} links.","source":source["url"]}); continue
            new=[x for x in items if x["url"] not in known]
            organ_new.extend(new); staged[key]=sorted(set(known)|set(current))
        if organ_new:
            unique=deduplicate(organ_new); report["new_items"]+=len(unique)
            if dry_run:
                print(format_message(organ,unique,maximum)); sent=True; code=StatusCode.DRY_RUN.value; reason="Mensagem simulada."
            elif not token or not chat_id:
                sent=False; code=StatusCode.TELEGRAM_NOT_CONFIGURED.value; reason="Configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID."
            else:
                result=send_message(token,chat_id,format_message(organ,unique,maximum)); sent=result.ok; code=result.code; reason=result.reason
            report["details"].append({"organ_id":oid,"code":code,"reason":reason})
            if sent:
                for key,value in staged.items():
                    if value != state.get("sources",{}).get(key,[]): report["state_changed"]=True
                    state.setdefault("sources",{})[key]=value
        else:
            for key,value in staged.items():
                if value != state.get("sources",{}).get(key,[]): report["state_changed"]=True
                state.setdefault("sources",{})[key]=value
    if report["new_items"]==0 and report["code"]==StatusCode.OK.value: report.update(code=StatusCode.NO_NEW_ITEMS.value,reason="Nenhuma publicação nova encontrada.")
    if report["state_changed"]:
        state.setdefault("metadata",{})["updated_at"]=datetime.now(timezone.utc).isoformat()
        atomic_write_json(state_path,state)
    atomic_write_json(last_path,report)
    return report

def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--dry-run",action="store_true"); args=parser.parse_args()
    report=run(dry_run=args.dry_run); print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
