from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

EVENT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("nomeacao", ("nomeação", "nomeacoes", "nomeados", "portaria de nomeação", "nomeia")),
    ("convocacao", ("convocação", "convocacoes", "convoca", "chamamento")),
    ("homologacao", ("homologação", "homologa", "resultado final homologado")),
    ("resultado", ("resultado final", "resultado preliminar", "classificação final", "classificacao final")),
    ("retificacao", ("retificação", "retificacao", "edital retificado")),
    ("edital", ("edital", "concurso público", "concurso publico")),
    ("inscricao", ("inscrição", "inscrições", "isencao", "isenção")),
    ("prorrogacao", ("prorrogação", "prorrogado", "prorroga")),
    ("banca", ("banca organizadora", "contratação da banca", "contratacao da banca")),
    ("comissao", ("comissão do concurso", "comissao do concurso", "comissão organizadora")),
    ("autorizacao", ("autorização", "autorizado", "autoriza concurso")),
    ("vacancia", ("vacância", "vacancia", "cargos vagos", "quadro de vagas")),
]

EVENT_STATUS = {
    "autorizacao": "Concurso autorizado",
    "comissao": "Comissão formada",
    "banca": "Banca definida",
    "edital": "Edital publicado",
    "retificacao": "Edital retificado",
    "inscricao": "Inscrições em andamento",
    "resultado": "Resultado publicado",
    "homologacao": "Homologado",
    "convocacao": "Convocações em andamento",
    "nomeacao": "Nomeações em andamento",
    "prorrogacao": "Validade prorrogada",
    "vacancia": "Vacância atualizada",
    "noticia": "Atualização localizada",
}

EVENT_PRIORITY = {
    "noticia": 0,
    "vacancia": 1,
    "autorizacao": 2,
    "comissao": 3,
    "banca": 4,
    "edital": 5,
    "retificacao": 6,
    "inscricao": 7,
    "resultado": 8,
    "homologacao": 9,
    "convocacao": 10,
    "nomeacao": 11,
    "prorrogacao": 12,
}

OFFICIAL_SUFFIXES = (".gov.br", ".edu.br", ".jus.br", ".leg.br", ".mp.br")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", normalized.casefold()).strip()


def classify_event(title: str, url: str = "", summary: str = "") -> str:
    text = normalize_text(f"{title} {url} {summary}")
    for event_type, keywords in EVENT_KEYWORDS:
        if any(normalize_text(keyword) in text for keyword in keywords):
            return event_type
    return "noticia"


def status_for_event(event_type: str) -> str:
    return EVENT_STATUS.get(event_type, EVENT_STATUS["noticia"])


def priority_for_event(event_type: str) -> int:
    return EVENT_PRIORITY.get(event_type, 0)


def configured_domains(organ: dict) -> set[str]:
    result: set[str] = set()
    for source in organ.get("alert_sources", []):
        host = urlsplit(source.get("url", "")).netloc.casefold().removeprefix("www.")
        if host:
            result.add(host)
    for host in organ.get("official_domains", []):
        value = str(host).casefold().removeprefix("www.").strip()
        if value:
            result.add(value)
    return result


def is_official_url(url: str, organ: dict | None = None) -> bool:
    host = urlsplit(url).netloc.casefold().removeprefix("www.")
    if not host:
        return False
    if host == "in.gov.br" or host.endswith(OFFICIAL_SUFFIXES):
        return True
    domains = configured_domains(organ or {})
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


def mentions_organ(text: str, organ: dict) -> bool:
    haystack = normalize_text(text)
    acronym = normalize_text(organ.get("acronym", ""))
    name = normalize_text(organ.get("name", ""))
    if acronym and len(acronym) >= 3 and re.search(rf"\b{re.escape(acronym)}\b", haystack):
        return True
    meaningful = [part for part in name.split() if len(part) > 3 and part not in {"federal", "estadual", "universidade", "instituto", "tribunal"}]
    return bool(name and name in haystack) or sum(part in haystack for part in meaningful[:6]) >= 2
