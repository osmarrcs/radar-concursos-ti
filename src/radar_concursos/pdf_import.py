from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .services import DEFAULT_VACANCY, save_contest, save_position, slugify
from .status_codes import StatusCode

_ROW_RE = re.compile(
    r"^\s*(\d{1,3})\s+(.*?)\s+(\d{1,2})\s*h/s\s+"
    r"(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})\s*$"
)


@dataclass(frozen=True)
class PdfAnalysis:
    metadata: dict[str, Any]
    positions: list[dict[str, Any]]
    text: str
    extraction_engine: str


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _month_number(name: str) -> int:
    months = {
        "janeiro": 1,
        "fevereiro": 2,
        "março": 3,
        "marco": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
    }
    return months[name.casefold()]


def _parse_portuguese_date(day: str, month: str, year: str) -> str:
    return date(int(year), _month_number(month), int(day)).isoformat()


def extract_pdf_text(path: str | Path) -> tuple[str, str]:
    """Extract text preserving table layout when possible.

    Priority:
    1. Poppler pdftotext -layout, normally available in Colab/GitHub runners.
    2. Optional pypdf fallback for environments without Poppler.
    """
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"PDF não encontrado: {source}")
    if source.suffix.casefold() != ".pdf":
        raise ValueError("O arquivo precisa ter extensão .pdf")

    executable = shutil.which("pdftotext")
    if executable:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "document.txt"
            completed = subprocess.run(
                [executable, "-layout", str(source), str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode == 0 and target.exists():
                text = target.read_text(encoding="utf-8", errors="replace")
                if text.strip():
                    return text, "pdftotext-layout"

    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Não foi possível ler o PDF. Instale o Poppler (pdftotext) ou o pacote pypdf."
        ) from exc

    reader = PdfReader(str(source))
    text = "\n\f\n".join((page.extract_text() or "") for page in reader.pages)
    if not text.strip():
        raise ValueError("O PDF não possui texto extraível. Pode ser necessário OCR.")
    return text, "pypdf"


def parse_edital_metadata(text: str, filename: str = "edital.pdf") -> dict[str, Any]:
    first_pages = text[:25000]
    edital_match = re.search(
        r"EDITAL\s+N[ºO°]?\s*([\w./-]+)\s*,?\s*DE\s+(\d{1,2})\s+DE\s+"
        r"([A-ZÇÃÕÉÊÍÓÔÚ]+)\s+DE\s+(\d{4})",
        first_pages,
        flags=re.IGNORECASE,
    )
    publication_match = re.search(
        r"Publicado\s+em\s*:\s*(\d{2})/(\d{2})/(\d{4})", first_pages, flags=re.IGNORECASE
    )
    organ_match = re.search(r"Órgão\s*:\s*[^\n/]*/([^\n]+)", first_pages, flags=re.IGNORECASE)
    title_match = re.search(
        r"(CONCURSO\s+PÚBLICO[^\n]*(?:\n\s*[A-ZÁÉÍÓÚÇÃÕ][A-ZÁÉÍÓÚÇÃÕ\- ]+)?)",
        first_pages,
        flags=re.IGNORECASE,
    )
    validity_match = re.search(
        r"prazo\s+de\s+validade[^.]{0,220}?([0-9]{1,2})\s*\([^)]*\)\s*anos?[^.]{0,180}?"
        r"(?:prorrogad[oa][^.]{0,80}?igual\s+período)?",
        first_pages,
        flags=re.IGNORECASE,
    )
    exam_match = re.search(
        r"provas?[^.]{0,160}?ser(?:á|ão)\s+(?:aplicad[ao]s?|realizad[ao]s?)[^.]{0,200}?\s(?:na|no|em)\s+([^.;]{1,140})",
        first_pages,
        flags=re.IGNORECASE,
    )

    year = int(edital_match.group(4)) if edital_match else date.today().year
    edital_number = edital_match.group(1) if edital_match else ""
    edital_date = (
        _parse_portuguese_date(edital_match.group(2), edital_match.group(3), edital_match.group(4))
        if edital_match
        else ""
    )
    publication_date = (
        date(int(publication_match.group(3)), int(publication_match.group(2)), int(publication_match.group(1))).isoformat()
        if publication_match
        else ""
    )
    validity_years = int(validity_match.group(1)) if validity_match else None
    title = _clean(title_match.group(1)) if title_match else f"Edital importado — {Path(filename).stem}"
    organ_name = _clean(organ_match.group(1)) if organ_match else ""
    return {
        "edital_number": edital_number,
        "edital_date": edital_date,
        "publication_date": publication_date,
        "year": year,
        "title": title,
        "organ_name_detected": organ_name,
        "validity_years": validity_years,
        "validity_rule": (
            f"{validity_years} {'ano' if validity_years == 1 else 'anos'} a partir da homologação do resultado final, conforme o edital."
            if validity_years
            else "Prazo de validade não identificado automaticamente."
        ),
        "exam_location": _clean(exam_match.group(1)) if exam_match else "",
        "filename": filename,
    }


def _split_position_specialty(value: str) -> tuple[str, str]:
    value = _clean(value)
    patterns = (
        r"\s*/\s*Área\s*:\s*",
        r"\s*/Área\s*:\s*",
        r"\s+Área\s*:\s*",
        r"\s*-\s*Área\s*/\s*",
        r"\s*/\s*Área\s*/\s*",
    )
    for pattern in patterns:
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match:
            return value[: match.start()].strip(" -/"), value[match.end() :].strip()
    return value, ""


def _lotation_from_line(line: str) -> str | None:
    match = re.search(r"Para\s+os\s+campi\s+de\s+(.+?)(?::|$)", line, flags=re.IGNORECASE)
    if match:
        return _clean(match.group(1))
    match = re.search(r"Para\s+o\s+campus\s+de\s+(.+?)(?::|$)", line, flags=re.IGNORECASE)
    if match:
        return _clean(match.group(1))
    return None


def parse_positions_from_text(text: str) -> list[dict[str, Any]]:
    """Parse common DOU-style cargo tables.

    The importer intentionally returns every detected position. It does not filter by IT keywords.
    The user chooses which positions to save in Colab.
    """
    start = re.search(r"\b2\.\s*DOS\s+CARGOS\s+E\s+VAGAS\b", text, flags=re.IGNORECASE)
    if not start:
        raise ValueError("A seção '2. DOS CARGOS E VAGAS' não foi localizada.")
    tail = text[start.start() :]
    end = re.search(r"\n\s*2\.2\.", tail)
    section = tail[: end.start()] if end else tail

    rows: list[dict[str, Any]] = []
    pending_prefix = ""
    pending_row: dict[str, Any] | None = None
    level = ""
    lotation = ""

    def finalize(row: dict[str, Any]) -> None:
        nonlocal pending_row
        position, specialty = _split_position_specialty(row.pop("raw_position"))
        row["position"] = position
        row["specialty"] = specialty
        rows.append(row)
        pending_row = None

    for raw in section.splitlines():
        line = _clean(raw)
        if not line:
            continue

        found_lotation = _lotation_from_line(line)
        if found_lotation is not None:
            lotation = found_lotation
            continue
        upper = line.upper()
        if "NÍVEL MÉDIO" in upper:
            level = "D"
            continue
        if "NÍVEL SUPERIOR" in upper:
            level = "E"
            continue
        if (
            not re.match(r"^\d+", line)
            and any(marker in upper for marker in ("Nº CARGO", "JORNADA DE", "TOTAL (*)", "(*) TOTAL", "VAGAS"))
        ):
            continue

        match = _ROW_RE.match(line)
        if match:
            if pending_row:
                finalize(pending_row)
            code, title, hours, total, ac, pn, pq, pi, pcd = match.groups()
            title = _clean(f"{pending_prefix} {title}")
            pending_prefix = ""
            row = {
                "position_code": code,
                "raw_position": title,
                "workload_hours": int(hours),
                "immediate_vacancies": int(total),
                "vacancy_breakdown": {
                    "AC": int(ac),
                    "PN": int(pn),
                    "PQ": int(pq),
                    "PI": int(pi),
                    "PCD": int(pcd),
                },
                "level": level,
                "lotation": lotation,
            }
            if re.search(r"(?:Área\s*:\s*|/\s*)$", title, flags=re.IGNORECASE):
                pending_row = row
            else:
                finalize(row)
            continue

        if pending_row:
            if line.startswith(("(*)", "2.", "NÍVEL")):
                finalize(pending_row)
            else:
                pending_row["raw_position"] = _clean(f"{pending_row['raw_position']} {line}")
                finalize(pending_row)
            continue

        if (
            re.search(r"(?:Tecnologia\s+da\s+Informação|/\s*Área\s*:|Área\s*:)", line, flags=re.IGNORECASE)
            and not re.match(r"^\d+", line)
        ):
            pending_prefix = line

    if pending_row:
        finalize(pending_row)
    if not rows:
        raise ValueError("Nenhuma linha de cargo/vaga foi reconhecida no edital.")
    return rows


def analyze_edital_pdf(path: str | Path) -> PdfAnalysis:
    text, engine = extract_pdf_text(path)
    return PdfAnalysis(
        metadata=parse_edital_metadata(text, Path(path).name),
        positions=parse_positions_from_text(text),
        text=text,
        extraction_engine=engine,
    )


def copy_attachment(source: str | Path, destination_root: str | Path, *, prefix: str = "edital", category: str = "editais") -> Path:
    source_path = Path(source)
    destination = Path(destination_root) / category
    destination.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}-{slugify(source_path.stem)}.pdf"
    target = destination / name
    shutil.copy2(source_path, target)
    return target


def import_selected_positions(
    analysis: PdfAnalysis,
    *,
    organ_id: str,
    selected_codes: list[str],
    attachment_relative_url: str,
    contest_title: str | None = None,
    data_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metadata = analysis.metadata
    edital_label = "Edital anexado"
    if metadata.get("edital_number"):
        edital_label = f"Edital nº {metadata['edital_number']}/{metadata['year']} anexado"
    contest = save_contest(
        {
            "organ_id": organ_id,
            "title": contest_title or metadata["title"],
            "year": metadata["year"],
            "status": "Edital publicado",
            "valid_until": "",
            "validity_years": metadata.get("validity_years"),
            "validity_rule": metadata.get("validity_rule", ""),
            "publication_date": metadata.get("publication_date", ""),
            "edital_date": metadata.get("edital_date", ""),
            "edital_number": metadata.get("edital_number", ""),
            "exam_location": metadata.get("exam_location", ""),
            "reserve_list": True,
            "lotation": "Conforme cargo e edital",
            "confidence": "alta",
            "is_official": True,
            "sources": [{"label": edital_label, "url": attachment_relative_url}],
            "collection_status": {
                "found": True,
                "code": StatusCode.OK.value,
                "reason": "Edital anexado e cargos importados; vacância e chamadas dependem de fontes separadas.",
                "source": "pdf_anexado",
            },
            "notes": (
                "O edital informa vagas, lotação e regra de validade. Vacância atual, último chamado e nota "
                "não são inferidos do edital e devem ser apurados em documentos próprios."
            ),
        },
        data_dir=data_dir,
    )
    selected = {str(code) for code in selected_codes}
    imported: list[dict[str, Any]] = []
    for row in analysis.positions:
        if str(row["position_code"]) not in selected:
            continue
        imported.append(
            save_position(
                {
                    "contest_id": contest["id"],
                    "position": row["position"],
                    "specialty": row.get("specialty", ""),
                    "position_code": row["position_code"],
                    "immediate_vacancies": row["immediate_vacancies"],
                    "workload_hours": row.get("workload_hours"),
                    "level": row.get("level", ""),
                    "lotation": row.get("lotation", ""),
                    "vacancy_breakdown": row.get("vacancy_breakdown", {}),
                    "last_called_rank": None,
                    "last_called_score": None,
                    "total_appointed": None,
                    "quota_type": "Todas as modalidades do edital",
                    "sources": [{"label": edital_label, "url": attachment_relative_url}],
                    "collection_status": {
                        "found": True,
                        "code": StatusCode.PARTIAL_DATA.value,
                        "reason": "Vaga extraída do edital; histórico de chamadas ainda não apurado.",
                        "source": "pdf_anexado",
                    },
                    "vacancy": DEFAULT_VACANCY,
                    "notes": "Cargo importado automaticamente do PDF e sujeito a conferência visual da tabela.",
                },
                data_dir=data_dir,
            )
        )
    return contest, imported
