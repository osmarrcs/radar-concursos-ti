from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from .alerts.parsers import normalize_url
from .search.classifier import priority_for_event, status_for_event

RELEVANT_EVENTS = {
    "autorizacao", "comissao", "banca", "edital", "retificacao", "inscricao",
    "resultado", "homologacao", "convocacao", "nomeacao", "prorrogacao", "vacancia",
}

YEAR_RE = re.compile(r"\b(20\d{2})\b")
EDITAL_RE = re.compile(r"edital(?:\s+n[ºo°.]*)?\s*[:\-]?\s*(\d{1,4})", re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_year(item: dict[str, Any]) -> int | None:
    text = " ".join(str(item.get(key) or "") for key in ("title", "url", "summary", "published_at"))
    years = [int(value) for value in YEAR_RE.findall(text)]
    plausible = [year for year in years if 2000 <= year <= datetime.now().year + 2]
    return max(plausible) if plausible else None


def extract_edital_number(item: dict[str, Any]) -> str:
    text = f"{item.get('title', '')} {item.get('summary', '')}"
    match = EDITAL_RE.search(text)
    return match.group(1) if match else ""


def discovery_id(organ_id: str, year: int | None, edital_number: str, url: str) -> str:
    suffix = edital_number or hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()[:10]
    return f"{organ_id}-{year or 'sem-ano'}-{suffix}"


def candidate_from_item(item: dict[str, Any]) -> dict[str, Any] | None:
    event = str(item.get("event_type") or "noticia")
    if event not in RELEVANT_EVENTS:
        return None
    organ_id = str(item.get("organ_id") or "").strip()
    url = normalize_url(str(item.get("url") or ""))
    if not organ_id or not url:
        return None
    year = extract_year(item)
    edital_number = extract_edital_number(item)
    timestamp = _now()
    return {
        "id": discovery_id(organ_id, year, edital_number, url),
        "organ_id": organ_id,
        "year": year,
        "edital_number": edital_number,
        "title": str(item.get("title") or "Publicação localizada"),
        "status": status_for_event(event),
        "event_type": event,
        "official": bool(item.get("official")),
        "confidence": str(item.get("confidence") or ("alta" if item.get("official") else "media")),
        "review_status": "pending",
        "structured": False,
        "first_discovered_at": str(item.get("discovered_at") or timestamp),
        "last_seen_at": timestamp,
        "sources": [{
            "label": str(item.get("source_label") or item.get("provider") or "Fonte localizada"),
            "url": url,
            "provider": str(item.get("provider") or ""),
            "published_at": str(item.get("published_at") or ""),
            "event_type": event,
            "official": bool(item.get("official")),
        }],
    }


def _merge_sources(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source in [*existing, *incoming]:
        url = normalize_url(str(source.get("url") or ""))
        if not url:
            continue
        current = merged.get(url)
        if current is None or (source.get("official") and not current.get("official")):
            source = dict(source)
            source["url"] = url
            merged[url] = source
    return sorted(merged.values(), key=lambda x: (str(x.get("published_at") or ""), bool(x.get("official"))), reverse=True)


def merge_candidate(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = dict(existing)
    old_priority = priority_for_event(str(existing.get("event_type") or "noticia"))
    new_priority = priority_for_event(str(incoming.get("event_type") or "noticia"))
    if new_priority >= old_priority:
        for key in ("title", "status", "event_type", "official", "confidence", "year", "edital_number"):
            if incoming.get(key) not in (None, ""):
                result[key] = incoming[key]
    result["official"] = bool(existing.get("official") or incoming.get("official"))
    result["last_seen_at"] = incoming.get("last_seen_at") or _now()
    result["sources"] = _merge_sources(existing.get("sources") or [], incoming.get("sources") or [])
    result.setdefault("first_discovered_at", incoming.get("first_discovered_at") or _now())
    result.setdefault("review_status", "pending")
    result.setdefault("structured", False)
    return result


def merge_discoveries(existing: list[dict[str, Any]], items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    indexed = {str(row["id"]): dict(row) for row in existing if row.get("id")}
    added = 0
    changed = 0
    for item in items:
        candidate = candidate_from_item(item)
        if candidate is None:
            continue
        current = indexed.get(candidate["id"])
        if current is None:
            indexed[candidate["id"]] = candidate
            added += 1
        else:
            merged = merge_candidate(current, candidate)
            if merged != current:
                indexed[candidate["id"]] = merged
                changed += 1
    rows = sorted(indexed.values(), key=lambda x: (x.get("year") or 0, x.get("last_seen_at") or ""), reverse=True)
    return rows, added, changed
