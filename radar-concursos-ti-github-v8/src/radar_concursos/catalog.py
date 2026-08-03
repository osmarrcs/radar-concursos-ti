from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

OPEN_STATUS_TERMS = (
    "edital publicado",
    "edital retificado",
    "inscricoes abertas",
    "inscrições abertas",
    "inscricoes em andamento",
    "inscrições em andamento",
)


def normalize(value: object) -> str:
    """Normalize user-visible text for accent-insensitive searches."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return re.sub(r"\s+", " ", text).strip()


def scope_matches(organ: dict[str, Any], scope_mode: str) -> bool:
    if scope_mode == "national":
        return organ.get("scope") == "national"
    if scope_mode == "states":
        return organ.get("scope") != "national"
    return True


def career_options(
    dataset: dict[str, Any], *, scope_mode: str = "", state: str = ""
) -> list[str]:
    careers = {
        str(item.get("career", "")).strip()
        for item in dataset.get("organs", {}).get("organs", [])
        if str(item.get("career", "")).strip()
        and scope_matches(item, scope_mode)
        and (not state or item.get("state") == state)
    }
    return sorted(careers, key=normalize)


def organ_options(
    dataset: dict[str, Any], *, scope_mode: str = "", state: str = "", career: str = ""
) -> list[dict[str, Any]]:
    organs = list(dataset.get("organs", {}).get("organs", []))
    organs = [item for item in organs if scope_matches(item, scope_mode)]
    if state:
        organs = [item for item in organs if str(item.get("state", "")).upper() == state.upper()]
    if career:
        organs = [item for item in organs if item.get("career") == career]
    return sorted(organs, key=lambda item: (normalize(item.get("acronym")), normalize(item.get("name"))))


def latest_contests(
    dataset: dict[str, Any], organ_id: str, *, limit: int | None = 3
) -> list[dict[str, Any]]:
    contests = [
        item
        for item in dataset.get("contests", {}).get("contests", [])
        if item.get("organ_id") == organ_id
    ]
    contests.sort(
        key=lambda item: (
            int(item.get("year") or 0),
            str(item.get("publication_date") or ""),
            str(item.get("edital_date") or ""),
            normalize(item.get("title")),
        ),
        reverse=True,
    )
    return contests if limit is None else contests[: max(0, int(limit))]


def positions_for_contest(dataset: dict[str, Any], contest_id: str) -> list[dict[str, Any]]:
    positions = [
        item
        for item in dataset.get("positions", {}).get("positions", [])
        if item.get("contest_id") == contest_id
    ]
    positions.sort(
        key=lambda item: (
            normalize(item.get("position")),
            normalize(item.get("specialty")),
            normalize(item.get("lotation")),
        )
    )
    return positions


def is_open_contest(contest: dict[str, Any], today: date | None = None) -> bool:
    current = today or date.today()
    status = normalize(contest.get("status"))
    application_end = str(contest.get("application_end") or "")
    if application_end:
        try:
            if date.fromisoformat(application_end) >= current:
                return True
        except ValueError:
            pass
    return any(normalize(term) in status for term in OPEN_STATUS_TERMS)


def open_contests(
    dataset: dict[str, Any], *, scope_mode: str = "", state: str = "", career: str = "", organ_id: str = ""
) -> list[dict[str, Any]]:
    organs = {item["id"]: item for item in dataset.get("organs", {}).get("organs", [])}
    result: list[dict[str, Any]] = []
    for contest in dataset.get("contests", {}).get("contests", []):
        organ = organs.get(contest.get("organ_id"))
        if not organ or not is_open_contest(contest):
            continue
        if organ_id and organ.get("id") != organ_id:
            continue
        if not scope_matches(organ, scope_mode):
            continue
        if state and organ.get("state") != state:
            continue
        if career and organ.get("career") != career:
            continue
        result.append({"contest": contest, "organ": organ})
    result.sort(
        key=lambda row: (
            int(row["contest"].get("year") or 0),
            str(row["contest"].get("publication_date") or ""),
            normalize(row["organ"].get("acronym")),
        ),
        reverse=True,
    )
    return result


def _joined_search_text(organ: dict[str, Any], contest: dict[str, Any], position: dict[str, Any]) -> str:
    vacancy = position.get("vacancy") or {}
    values = [
        organ.get("name"), organ.get("acronym"), organ.get("career"), organ.get("sphere"),
        organ.get("scope"), organ.get("state"), organ.get("city"), contest.get("title"),
        contest.get("year"), contest.get("status"), contest.get("edital_number"),
        contest.get("exam_location"), contest.get("lotation"), contest.get("notes"),
        position.get("position"), position.get("specialty"), position.get("position_code"),
        position.get("lotation"), position.get("level"), position.get("workload_hours"),
        position.get("quota_type"), position.get("last_called_name"), vacancy.get("reason"),
    ]
    return normalize(" ".join(str(value or "") for value in values))


def search_catalog(
    dataset: dict[str, Any], *, query: str = "", state: str = "", scope_mode: str = "",
    career: str = "", organ_id: str = "", limit: int = 200,
) -> list[dict[str, Any]]:
    """Search all locally stored organs, contests and positions without prior selection."""
    terms = [part for part in normalize(query).split(" ") if part]
    organs = {item["id"]: item for item in dataset.get("organs", {}).get("organs", [])}
    contests = {item["id"]: item for item in dataset.get("contests", {}).get("contests", [])}
    results: list[dict[str, Any]] = []
    for position in dataset.get("positions", {}).get("positions", []):
        contest = contests.get(position.get("contest_id"))
        if not contest:
            continue
        organ = organs.get(contest.get("organ_id"))
        if not organ:
            continue
        if organ_id and organ.get("id") != organ_id:
            continue
        if not scope_matches(organ, scope_mode):
            continue
        if state and organ.get("state") != state:
            continue
        if career and organ.get("career") != career:
            continue
        haystack = _joined_search_text(organ, contest, position)
        if terms and not all(term in haystack for term in terms):
            continue
        results.append({"organ": organ, "contest": contest, "position": position})
    results.sort(
        key=lambda row: (
            int(row["contest"].get("year") or 0),
            normalize(row["organ"].get("acronym")),
            normalize(row["position"].get("position")),
            normalize(row["position"].get("specialty")),
        ),
        reverse=True,
    )
    return results[: max(1, int(limit))]
