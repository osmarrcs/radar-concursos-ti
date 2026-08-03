from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        selected = [
            provider for provider in self.providers
            if enabled_providers is None or provider.name in enabled_providers
        ]

        def run_provider(provider: Any):
            options = dict((provider_options or {}).get(provider.name, {}))
            return provider.search(
                organ, keywords=keywords, days=days, max_results=max_results, **options
            )

        if selected:
            with ThreadPoolExecutor(max_workers=min(3, len(selected))) as executor:
                futures = {executor.submit(run_provider, provider): provider.name for provider in selected}
                for future in as_completed(futures):
                    items, metrics = future.result()
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

    def search_organs(
        self,
        organs: Iterable[dict],
        *,
        keywords: list[str],
        days: int = 90,
        max_results: int = 50,
        enabled_providers: set[str] | None = None,
        provider_options: dict[str, dict[str, Any]] | None = None,
        query_label: str = "Busca geral",
    ) -> SearchReport:
        """Search several registered organs and merge their results.

        This powers the Colab general search without requiring the user to know the
        exact organ first. Each returned item keeps the organ_id that produced it.
        """
        started = time.perf_counter()
        organ_list = list(organs)
        reports: list[SearchReport] = []
        if organ_list:
            with ThreadPoolExecutor(max_workers=min(4, len(organ_list))) as executor:
                futures = [
                    executor.submit(
                        self.search_organ, organ, keywords=keywords, days=days,
                        max_results=max_results, enabled_providers=enabled_providers,
                        provider_options=provider_options,
                    )
                    for organ in organ_list
                ]
                for future in as_completed(futures):
                    reports.append(future.result())

        deduped: dict[str, dict[str, Any]] = {}
        errors: list[dict[str, str]] = []
        providers: list[dict[str, Any]] = []
        for report in reports:
            errors.extend(report.errors)
            providers.extend(report.metrics.get("providers", []))
            for item in report.items:
                key = normalize_url(item.get("url", ""))
                current = deduped.get(key)
                if current is None or (item.get("official") and not current.get("official")):
                    deduped[key] = item

        items = sorted(
            deduped.values(),
            key=lambda item: (item.get("published_at") or "", bool(item.get("official")), str(item.get("title", "")).casefold()),
            reverse=True,
        )
        elapsed = round((time.perf_counter() - started) * 1000)
        metrics = {
            "duration_ms": elapsed,
            "organs_searched": len(reports),
            "providers_enabled": sum(int(report.metrics.get("providers_enabled", 0)) for report in reports),
            "provider_attempts": sum(int(report.metrics.get("provider_attempts", 0)) for report in reports),
            "provider_successes": sum(int(report.metrics.get("provider_successes", 0)) for report in reports),
            "provider_failures": sum(int(report.metrics.get("provider_failures", 0)) for report in reports),
            "items_scanned": sum(int(report.metrics.get("items_scanned", 0)) for report in reports),
            "relevant_items": len(items),
            "official_items": sum(1 for item in items if item.get("official")),
            "errors": len(errors),
            "providers": providers,
        }
        return SearchReport(
            organ_id="__multiple__",
            query=query_label,
            items=items[: max(1, int(max_results))],
            metrics=metrics,
            errors=errors,
            searched_at=datetime.now(timezone.utc).isoformat(),
        )

