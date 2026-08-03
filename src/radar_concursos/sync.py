from __future__ import annotations

import argparse
import json
import time
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .discovery import merge_discoveries
from .repository import DATA_DIR, atomic_write_json, load_json
from .pdf_import import analyze_edital_pdf, import_selected_positions
from .search.orchestrator import SearchOrchestrator
from .services import save_search_updates

DEFAULT_KEYWORDS = [
    "concurso", "edital", "inscrições", "retificação", "resultado final", "homologação",
    "convocação", "nomeação", "prorrogação", "comissão", "banca", "autorização",
    "vacância", "cargos vagos", "tecnologia da informação", "analista", "técnico",
]


def _download_pdf(url: str, target: Path, timeout: int = 35, max_bytes: int = 25 * 1024 * 1024) -> None:
    request = Request(url, headers={"User-Agent": "radar-concursos-ti/1.4 (+GitHub Actions)"})
    with urlopen(request, timeout=timeout) as response:
        content_type = str(response.headers.get("Content-Type") or "").lower()
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("PDF excede o limite de 25 MB.")
    if not data.startswith(b"%PDF") and "pdf" not in content_type:
        raise ValueError("A URL não retornou um documento PDF.")
    target.write_bytes(data)


def _already_structured(data_dir: Path, organ_id: str, year: int | None, edital_number: str) -> bool:
    contests = load_json(data_dir / "contests.json").get("contests") or []
    for contest in contests:
        if contest.get("organ_id") != organ_id:
            continue
        if year and contest.get("year") != year:
            continue
        if edital_number and str(contest.get("edital_number") or "").strip() != edital_number:
            continue
        return True
    return False


def _auto_import_pdf_discoveries(data_dir: Path, discoveries: list[dict[str, Any]]) -> tuple[int, list[dict[str, str]]]:
    imported = 0
    errors: list[dict[str, str]] = []
    for candidate in discoveries:
        if candidate.get("structured") or not candidate.get("official") or candidate.get("event_type") != "edital":
            continue
        if _already_structured(data_dir, candidate.get("organ_id", ""), candidate.get("year"), str(candidate.get("edital_number") or "")):
            candidate["structured"] = True
            candidate["review_status"] = "already_structured"
            continue
        sources = candidate.get("sources") or []
        source = next((x for x in sources if ".pdf" in str(x.get("url") or "").lower()), None)
        if not source:
            continue
        url = str(source.get("url") or "")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "edital.pdf"
                _download_pdf(url, path)
                analysis = analyze_edital_pdf(path)
                codes = [str(row["position_code"]) for row in analysis.positions]
                contest, positions = import_selected_positions(
                    analysis, organ_id=str(candidate["organ_id"]), selected_codes=codes,
                    attachment_relative_url=url, data_dir=data_dir,
                )
            candidate["structured"] = True
            candidate["structured_contest_id"] = contest["id"]
            candidate["review_status"] = "auto_imported_review_recommended"
            candidate["positions_imported"] = len(positions)
            imported += 1
        except Exception as exc:
            candidate["review_status"] = "pdf_parser_failed"
            candidate["last_import_error"] = str(exc)[:500]
            errors.append({"discovery_id": str(candidate.get("id")), "url": url, "reason": str(exc)})
    return imported, errors


def _load_or_create_discoveries(data_dir: Path) -> dict[str, Any]:
    path = data_dir / "discovered_contests.json"
    if path.exists():
        return load_json(path)
    payload = {
        "metadata": {
            "schema_version": "1.0",
            "description": "Concursos e eventos descobertos automaticamente, ainda não estruturados/revisados.",
        },
        "discoveries": [],
    }
    atomic_write_json(path, payload)
    return payload


def sync_organs(
    *,
    data_dir: Path = DATA_DIR,
    organ_ids: list[str] | None = None,
    days: int = 730,
    max_results: int = 80,
    enabled_providers: set[str] | None = None,
    orchestrator: SearchOrchestrator | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    organs_payload = load_json(data_dir / "organs.json")
    all_organs = organs_payload.get("organs") or []
    selected = [organ for organ in all_organs if not organ_ids or organ.get("id") in set(organ_ids)]
    engine = orchestrator or SearchOrchestrator()
    all_items: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    totals = {
        "organs_requested": len(selected),
        "organs_succeeded": 0,
        "provider_attempts": 0,
        "provider_successes": 0,
        "provider_failures": 0,
        "items_scanned": 0,
        "relevant_items": 0,
        "official_items": 0,
        "errors": 0,
    }
    providers = enabled_providers or {"fontes_oficiais", "gdelt", "querido_diario"}

    def search_one(organ: dict[str, Any]):
        return organ, engine.search_organ(
            organ, keywords=DEFAULT_KEYWORDS, days=days, max_results=max_results,
            enabled_providers=providers,
        )

    with ThreadPoolExecutor(max_workers=min(4, max(1, len(selected)))) as executor:
        futures = [executor.submit(search_one, organ) for organ in selected]
        for future in as_completed(futures):
            organ, report = future.result()
            all_items.extend(report.items)
            metrics = report.metrics
            if int(metrics.get("provider_successes", 0)) > 0:
                totals["organs_succeeded"] += 1
            for key in ("provider_attempts", "provider_successes", "provider_failures", "items_scanned", "relevant_items", "official_items", "errors"):
                totals[key] += int(metrics.get(key, 0))
            details.append({
                "organ_id": organ.get("id"),
                "organ": organ.get("acronym") or organ.get("name"),
                "items": len(report.items),
                "official_items": int(metrics.get("official_items", 0)),
                "errors": report.errors,
            })

    saved_updates = save_search_updates(all_items, auto_apply=False, data_dir=data_dir)
    discoveries_payload = _load_or_create_discoveries(data_dir)
    merged, added, changed = merge_discoveries(discoveries_payload.get("discoveries") or [], all_items)
    discoveries_payload.setdefault("metadata", {})["updated_at"] = datetime.now(timezone.utc).isoformat()
    discoveries_payload["discoveries"] = merged
    atomic_write_json(data_dir / "discovered_contests.json", discoveries_payload)

    auto_imported, import_errors = _auto_import_pdf_discoveries(data_dir, merged)
    if auto_imported or import_errors:
        discoveries_payload["discoveries"] = merged
        discoveries_payload["metadata"]["updated_at"] = datetime.now(timezone.utc).isoformat()
        atomic_write_json(data_dir / "discovered_contests.json", discoveries_payload)

    report = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            **totals,
            "updates_added": int(saved_updates.get("added_count", 0)),
            "discoveries_added": added,
            "discoveries_changed": changed,
            "discoveries_total": len(merged),
            "pdfs_auto_imported": auto_imported,
            "pdf_import_errors": len(import_errors),
            "duration_ms": round((time.perf_counter() - started) * 1000),
        },
        "details": details,
        "pdf_import_errors": import_errors,
    }
    atomic_write_json(data_dir / "sync_last_run.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza publicações e concursos descobertos automaticamente.")
    parser.add_argument("--organ", action="append", dest="organs", help="ID de órgão; pode repetir. Sem uso, consulta todos.")
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--max-results", type=int, default=80)
    parser.add_argument("--providers", default="fontes_oficiais,gdelt,querido_diario")
    args = parser.parse_args()
    providers = {value.strip() for value in args.providers.split(",") if value.strip()}
    report = sync_organs(organ_ids=args.organs, days=args.days, max_results=args.max_results, enabled_providers=providers)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
