from __future__ import annotations
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from .status import SearchStatus

BASE_URL = "https://api.queridodiario.ok.org.br/gazettes"

def search_gazettes(query: str, territory_id: str, size: int = 10, timeout: int = 30) -> tuple[list[dict], SearchStatus]:
    params = {"querystring": query, "territory_ids": territory_id, "size": size}
    url = f"{BASE_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent":"radar-concursos-ti/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return [], SearchStatus(False,"HTTP_ERROR",f"HTTP {exc.code} ao consultar Querido Diário.","querido_diario",exc.code)
    except TimeoutError:
        return [], SearchStatus(False,"TIMEOUT","A API não respondeu dentro do limite configurado.","querido_diario")
    except URLError as exc:
        return [], SearchStatus(False,"NETWORK_ERROR",f"Falha de rede: {exc.reason}","querido_diario")
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as exc:
        return [], SearchStatus(False,"INVALID_RESPONSE",f"Resposta inesperada: {exc}","querido_diario")
    rows = payload.get("gazettes") or payload.get("items") or []
    if not rows:
        return [], SearchStatus(False,"NO_RESULTS","A consulta foi aceita, mas não retornou publicações.","querido_diario",200)
    return rows, SearchStatus(True,"OK",f"{len(rows)} publicação(ões) encontrada(s).","querido_diario",200)
