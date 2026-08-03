from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from html import unescape
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..alerts.parsers import deduplicate, parse_feed, parse_html
from .classifier import classify_event, is_official_url, mentions_organ, normalize_text
from .models import ProviderMetrics, SearchItem

TextFetcher = Callable[[str, int], str]
JsonFetcher = Callable[[str, int], dict]

STATE_NAMES={"PE":"Pernambuco","PB":"Paraíba","AL":"Alagoas","RN":"Rio Grande do Norte","SE":"Sergipe","CE":"Ceará","MA":"Maranhão","BR":"Brasil"}


def fetch_text(url: str, timeout: int = 25) -> str:
    request = Request(url, headers={"User-Agent": "radar-concursos-ti/1.1 (+GitHub Actions)"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_json(url: str, timeout: int = 25) -> dict:
    return json.loads(fetch_text(url, timeout))


def _error(metrics: ProviderMetrics, source: str, exc: Exception) -> None:
    metrics.failed += 1
    code = "HTTP_ERROR" if isinstance(exc, HTTPError) else "NETWORK_ERROR" if isinstance(exc, (URLError, TimeoutError)) else "PARSER_ERROR"
    metrics.errors.append({"source": source, "code": code, "reason": str(exc)})



def expand_keywords(keywords: list[str]) -> list[str]:
    """Expand free-text phrases into usable search terms without requiring an exact sentence."""
    result: list[str] = []
    for raw in keywords:
        value = str(raw or "").strip()
        if not value:
            continue
        result.append(value)
        for token in normalize_text(value).split():
            if len(token) >= 4:
                result.append(token)
    return list(dict.fromkeys(result))

def _relevant(title: str, url: str, keywords: list[str], organ: dict) -> bool:
    text = normalize_text(f"{title} {url}")
    has_keyword = any(normalize_text(word) in text for word in expand_keywords(keywords))
    return has_keyword and (mentions_organ(text, organ) or is_official_url(url, organ))


class ConfiguredSourceProvider:
    name = "fontes_oficiais"

    def search(self, organ: dict, *, keywords: list[str], timeout: int = 25, fetcher: TextFetcher = fetch_text, **_: object) -> tuple[list[SearchItem], ProviderMetrics]:
        started = time.perf_counter()
        metrics = ProviderMetrics(provider=self.name)
        result: list[SearchItem] = []
        for source in organ.get("alert_sources", []):
            metrics.attempted += 1
            url = source.get("url", "")
            try:
                content = fetcher(url, timeout)
                items = parse_feed(content, url) if source.get("type") in {"rss", "atom", "feed"} else parse_html(content, url)
                metrics.succeeded += 1
                metrics.items_scanned += len(items)
                for item in deduplicate(items):
                    if not _relevant(item.get("title", ""), item.get("url", ""), keywords, organ):
                        continue
                    official = True
                    metrics.relevant_items += 1
                    metrics.official_items += 1
                    result.append(SearchItem(
                        organ_id=organ["id"], title=item.get("title") or item["url"], url=item["url"],
                        event_type=classify_event(item.get("title", ""), item["url"], item.get("summary", "")),
                        provider=self.name, source_label=source.get("label", "Fonte oficial"),
                        published_at=item.get("published_at", ""), summary=item.get("summary", ""),
                        official=official, confidence="alta",
                    ))
            except Exception as exc:
                _error(metrics, url, exc)
        metrics.duration_ms = round((time.perf_counter() - started) * 1000)
        return result, metrics


class GdeltProvider:
    name = "gdelt"
    endpoint = "https://api.gdeltproject.org/api/v2/doc/doc"

    def search(self, organ: dict, *, keywords: list[str], days: int = 90, max_results: int = 50, timeout: int = 25, json_fetcher: JsonFetcher = fetch_json, **_: object) -> tuple[list[SearchItem], ProviderMetrics]:
        started = time.perf_counter()
        metrics = ProviderMetrics(provider=self.name, attempted=1)
        terms = [f'"{organ.get("acronym", "")}"', f'"{organ.get("name", "")}"']
        key_terms = [word for word in expand_keywords(keywords) if len(word) >= 5][:12]
        region = organ.get("city") or STATE_NAMES.get(str(organ.get("state", "")).upper(), "")
        region_clause = f' "{region}"' if region and str(organ.get("scope")) != "national" else ""
        query = f"({' OR '.join(terms)}) ({' OR '.join(key_terms)}){region_clause}"
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "sort": "DateDesc",
            "maxrecords": max(10, min(int(max_results), 250)),
            "timespan": f"{max(1, min(int(days), 365))}days",
        }
        url = f"{self.endpoint}?{urlencode(params)}"
        result: list[SearchItem] = []
        try:
            payload = json_fetcher(url, timeout)
            articles = payload.get("articles", []) if isinstance(payload, dict) else []
            if not isinstance(articles, list):
                raise ValueError("Resposta GDELT sem lista articles.")
            metrics.succeeded = 1
            metrics.items_scanned = len(articles)
            for article in articles:
                title = unescape(str(article.get("title", "")).strip())
                item_url = str(article.get("url", "")).strip()
                if not title or not item_url or not _relevant(title, item_url, keywords, organ):
                    continue
                official = is_official_url(item_url, organ)
                metrics.relevant_items += 1
                metrics.official_items += int(official)
                seen = str(article.get("seendate", ""))
                published = ""
                try:
                    published = datetime.strptime(seen[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc).isoformat()
                except (ValueError, TypeError):
                    published = seen
                result.append(SearchItem(
                    organ_id=organ["id"], title=title, url=item_url,
                    event_type=classify_event(title, item_url), provider=self.name,
                    source_label=str(article.get("domain", "GDELT")), published_at=published,
                    official=official, confidence="alta" if official else "media",
                ))
        except Exception as exc:
            _error(metrics, url, exc)
        metrics.duration_ms = round((time.perf_counter() - started) * 1000)
        return result, metrics


class QueridoDiarioProvider:
    name = "querido_diario"
    endpoint = "https://api.queridodiario.ok.org.br/gazettes"

    def search(self, organ: dict, *, keywords: list[str], days: int = 90, max_results: int = 50, timeout: int = 25, json_fetcher: JsonFetcher = fetch_json, **_: object) -> tuple[list[SearchItem], ProviderMetrics]:
        started = time.perf_counter()
        metrics = ProviderMetrics(provider=self.name)
        territory_id = str(organ.get("territory_id", "")).strip()
        if not territory_id:
            metrics.duration_ms = round((time.perf_counter() - started) * 1000)
            return [], metrics
        metrics.attempted = 1
        published_since = (date.today() - timedelta(days=max(1, min(int(days), 3650)))).isoformat()
        params = {
            "territory_ids": territory_id,
            "querystring": "concurso",
            "published_since": published_since,
            "excerpt_size": 500,
            "number_of_excerpts": 2,
            "size": max(10, min(int(max_results), 100)),
        }
        url = f"{self.endpoint}?{urlencode(params)}"
        result: list[SearchItem] = []
        try:
            payload = json_fetcher(url, timeout)
            gazettes = payload.get("gazettes", []) if isinstance(payload, dict) else []
            if not isinstance(gazettes, list):
                raise ValueError("Resposta do Querido Diário sem lista gazettes.")
            metrics.succeeded = 1
            metrics.items_scanned = len(gazettes)
            for gazette in gazettes:
                excerpts = gazette.get("excerpts") or []
                if isinstance(excerpts, str):
                    excerpts = [excerpts]
                summary = " ".join(str(x) for x in excerpts)
                title = f"Diário oficial de {gazette.get('territory_name') or organ.get('city') or organ.get('acronym')} — {gazette.get('date', '')}"
                item_url = str(gazette.get("url") or gazette.get("file_raw") or gazette.get("file_url") or "").strip()
                if not item_url or not any(normalize_text(word) in normalize_text(summary) for word in expand_keywords(keywords)):
                    continue
                metrics.relevant_items += 1
                metrics.official_items += 1
                result.append(SearchItem(
                    organ_id=organ["id"], title=title, url=item_url,
                    event_type=classify_event(title, item_url, summary), provider=self.name,
                    source_label="Querido Diário", published_at=str(gazette.get("date", "")),
                    summary=summary[:1000], official=True, confidence="alta",
                ))
        except Exception as exc:
            _error(metrics, url, exc)
        metrics.duration_ms = round((time.perf_counter() - started) * 1000)
        return result, metrics
