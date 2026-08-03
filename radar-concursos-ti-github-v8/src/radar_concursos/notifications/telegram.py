from __future__ import annotations
import json
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from ..status_codes import StatusCode

@dataclass(frozen=True)
class TelegramResult:
    ok: bool
    code: str
    reason: str
    message_id: int|None=None

def send_message(token: str, chat_id: str, text: str, timeout: int=20) -> TelegramResult:
    if not token or not chat_id:
        return TelegramResult(False,StatusCode.TELEGRAM_NOT_CONFIGURED.value,"Token ou Chat ID não configurado.")
    url=f"https://api.telegram.org/bot{token}/sendMessage"
    data=urlencode({"chat_id":chat_id,"text":text,"disable_web_page_preview":"true"}).encode()
    try:
        with urlopen(Request(url,data=data,headers={"User-Agent":"radar-concursos-ti/0.9"}),timeout=timeout) as response:
            payload=json.loads(response.read().decode("utf-8"))
    except HTTPError as exc: return TelegramResult(False,StatusCode.HTTP_ERROR.value,f"Telegram respondeu HTTP {exc.code}.")
    except (URLError,TimeoutError) as exc: return TelegramResult(False,StatusCode.NETWORK_ERROR.value,str(exc))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc: return TelegramResult(False,StatusCode.INVALID_RESPONSE.value,str(exc))
    if not payload.get("ok"): return TelegramResult(False,StatusCode.INVALID_RESPONSE.value,str(payload.get("description","Resposta inválida.")))
    msg_id=payload.get("result",{}).get("message_id")
    return TelegramResult(True,StatusCode.OK.value,"Mensagem enviada.",msg_id)
