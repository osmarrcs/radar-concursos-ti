from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from ..alerts.parsers import normalize_url
from .models import ProviderMetrics, SearchItem
from .providers import ConfiguredSourceProvider, GdeltProvider, QueridoDiarioProvider


@dataclass(frozen=True)
class SearchReport:
    organ_id: str
    query: str
    items: list[dict[str, Any]]
    metrics: dict[str, Any]
    errors: list[dict[str, str]]
    searched_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SearchOrchestrator:
    def __init__(self, providers: Iterable[Any] | None = None) -> None:
        self.providers = list(providers or [ConfiguredSourceProvider(), GdeltProvider(), QueridoDiarioProvider()])

    def search_organ(
        self,
        organ: dict,
        *,
        keywords: list[str],
        days: int = 90,
        max_results: int = 50,
        enabled_providers: set[str] | None = None,
        provider_options: dict[str, dict[str, Any]] | None = None,
    ) -> SearchReport:
        started = time.perf_counter()
        all_items: list[SearchItem] = []
        provider_metrics: list[ProviderMetrics] = []
        errors: list[dict[str, str]] = []
        for provider in self.providers:
            if enabled_providers is not None and provider.name not in enabled_providers:
                continue
            options = dict((provider_options or {}).get(provider.name, {}))
            items, metrics = provider.search(
                organ,
                keywords=keywords,
                days=days,
                max_results=max_results,
                **options,
            )
            all_items.extend(items)
            provider_metrics.append(metrics)
            errors.extend(metrics.errors)

        deduped: dict[str, SearchItem] = {}
        for item in all_items:
            key = normalize_url(item.url)
            current = deduped.get(key)
            if current is None or (item.official and not current.official):
                deduped[key] = item
        items = sorted(
            deduped.values(),
            key=lambda item: (item.published_at or "", item.official, item.title.casefold()),
            reverse=True,
        )
        elapsed = round((time.perf_counter() - started) * 1000)
        metrics = {
            "duration_ms": elapsed,
            "providers_enabled": len(provider_metrics),
            "provider_attempts": sum(x.attempted for x in provider_metrics),
            "provider_successes": sum(x.succeeded for x in provider_metrics),
            "provider_failures": sum(x.failed for x in provider_metrics),
            "items_scanned": sum(x.items_scanned for x in provider_metrics),
            "relevant_items": len(items),
            "official_items": sum(1 for x in items if x.official),
            "errors": len(errors),
            "providers": [x.to_dict() for x in provider_metrics],
        }
        query = f"{organ.get('state', '')}/{organ.get('acronym', '') or organ.get('name', '')}".strip("/")
        return SearchReport(
            organ_id=organ["id"],
            query=query,
            items=[item.to_dict() for item in items],
            metrics=metrics,
            errors=errors,
            searched_at=datetime.now(timezone.utc).isoformat(),
        )
