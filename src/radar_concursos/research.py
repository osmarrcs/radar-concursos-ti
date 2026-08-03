from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from .search.orchestrator import SearchOrchestrator


@dataclass
class MetricResearchResult:
    position_id: str
    position_label: str
    vacancy: Any
    last_called_name: str
    last_called_rank: Any
    last_called_score: Any
    total_appointed: Any
    status_code: str
    status_reason: str
    evidence: dict[str, list[dict[str, Any]]]
    search_metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def position_label(position: dict[str, Any]) -> str:
    label = str(position.get("position") or "Cargo")
    if position.get("specialty"):
        label += f" / {position['specialty']}"
    return label


def metric_keywords(organ: dict[str, Any], contest: dict[str, Any], position: dict[str, Any]) -> list[str]:
    values = [
        organ.get("acronym"),
        organ.get("name"),
        str(contest.get("year") or ""),
        contest.get("edital_number"),
        position.get("position"),
        position.get("specialty"),
        "vacância cargos vagos quadro de pessoal",
        "convocação nomeação último convocado",
        "resultado final classificação nota",
    ]
    return [str(value).strip() for value in values if str(value or "").strip()]


def _group_evidence(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {"vacancia": [], "chamadas": [], "resultado": [], "outros": []}
    for item in items:
        event = item.get("event_type") or "noticia"
        if event == "vacancia":
            groups["vacancia"].append(item)
        elif event in {"convocacao", "nomeacao"}:
            groups["chamadas"].append(item)
        elif event in {"resultado", "homologacao"}:
            groups["resultado"].append(item)
        else:
            groups["outros"].append(item)
    return {key: value[:8] for key, value in groups.items()}


def research_position_metrics(
    organ: dict[str, Any],
    contest: dict[str, Any],
    position: dict[str, Any],
    *,
    orchestrator: SearchOrchestrator | None = None,
    days: int = 730,
    enabled_providers: set[str] | None = None,
) -> MetricResearchResult:
    engine = orchestrator or SearchOrchestrator()
    report = engine.search_organ(
        organ,
        keywords=metric_keywords(organ, contest, position),
        days=days,
        max_results=80,
        enabled_providers=enabled_providers,
    )
    vacancy = (position.get("vacancy") or {}).get("count")
    name = str(position.get("last_called_name") or "")
    rank = position.get("last_called_rank")
    score = position.get("last_called_score")
    appointed = position.get("total_appointed")
    present = sum(value not in (None, "") for value in (vacancy, name, rank, score))
    evidence = _group_evidence(report.items)
    evidence_count = sum(len(value) for value in evidence.values())
    if present >= 4:
        code = "OK"
        reason = "Vacância, último convocado, classificação e nota já constam na base estruturada."
    elif present:
        code = "PARTIAL_DATA"
        reason = "Parte das métricas está estruturada; os links encontrados ajudam a completar a conferência."
    elif evidence_count:
        code = "MANUAL_REVIEW_REQUIRED"
        reason = "A pesquisa encontrou documentos candidatos, mas não é seguro extrair automaticamente nome, nota e vacância de formatos diferentes sem validação."
    else:
        code = "NO_RESULTS"
        reason = "Nenhuma evidência relevante foi localizada pelos provedores habilitados."
    return MetricResearchResult(
        position_id=position["id"],
        position_label=position_label(position),
        vacancy=vacancy,
        last_called_name=name,
        last_called_rank=rank,
        last_called_score=score,
        total_appointed=appointed,
        status_code=code,
        status_reason=reason,
        evidence=evidence,
        search_metrics=report.metrics,
    )


def research_selected_positions(
    organ: dict[str, Any],
    contest: dict[str, Any],
    positions: list[dict[str, Any]],
    *,
    orchestrator: SearchOrchestrator | None = None,
    days: int = 730,
    enabled_providers: set[str] | None = None,
) -> list[MetricResearchResult]:
    if not positions:
        raise ValueError("Selecione ao menos um cargo.")
    if len(positions) > 2:
        raise ValueError("Selecione no máximo dois cargos/especialidades por edital.")
    engine = orchestrator or SearchOrchestrator()
    return [
        research_position_metrics(
            organ,
            contest,
            position,
            orchestrator=engine,
            days=days,
            enabled_providers=enabled_providers,
        )
        for position in positions
    ]
