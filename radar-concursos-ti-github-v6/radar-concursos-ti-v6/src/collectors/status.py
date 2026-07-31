from dataclasses import dataclass, asdict

@dataclass
class SearchStatus:
    found: bool
    code: str
    reason: str
    source: str
    http_status: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

ERROR_CODES = {
    "OK": "Consulta concluída e registros encontrados.",
    "NO_RESULTS": "A fonte respondeu, mas não retornou resultados para os termos e período.",
    "SOURCE_NOT_CONFIGURED": "O órgão ainda não possui fonte de busca configurada.",
    "MUNICIPALITY_NOT_COVERED": "O município não foi localizado na cobertura da API consultada.",
    "HTTP_ERROR": "A fonte respondeu com erro HTTP.",
    "TIMEOUT": "A fonte excedeu o tempo máximo de resposta.",
    "NETWORK_ERROR": "Falha de rede, DNS ou conexão TLS.",
    "INVALID_RESPONSE": "A resposta não tinha o formato esperado.",
    "PARSER_ERROR": "O documento foi obtido, mas não pôde ser interpretado.",
    "MISSING_OFFICIAL_SOURCE": "Há menção ao concurso, mas falta fonte oficial suficiente para confirmar o dado.",
    "MANUAL_REVIEW_REQUIRED": "O cruzamento de classificação e nomeação precisa de revisão manual.",
}
