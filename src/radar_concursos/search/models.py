from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class SearchItem:
    organ_id: str
    title: str
    url: str
    event_type: str
    provider: str
    source_label: str = ""
    published_at: str = ""
    summary: str = ""
    official: bool = False
    confidence: str = "media"
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProviderMetrics:
    provider: str
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    items_scanned: int = 0
    relevant_items: int = 0
    official_items: int = 0
    duration_ms: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
