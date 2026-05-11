import os
from enum import Enum

CAMARA_API_BASE_URL = os.getenv("CAMARA_API_BASE_URL", "https://dadosabertos.camara.leg.br/api/v2/")

DOMAINS_EARLIEST_DATES = {
    "deputados": "1826-04-29",
    "proposicoes": "1988-01-01",
    "votacoes": "1991-01-01",
    "despesas": "2009-01-01",
}


class ApiRoutes(str, Enum):
    """Mapeamento oficial dos endpoints raiz da API da Câmara."""

    BLOCOS = "blocos"
    DEPUTADOS = "deputados"
    EVENTOS = "eventos"
    FRENTES = "frentes"
    GRUPOS = "grupos"
    LEGISLATURAS = "legislaturas"
    ORGAOS = "orgaos"
    PARTIDOS = "partidos"
    PROPOSICOES = "proposicoes"
    VOTACOES = "votacoes"
    REFERENCIAS = "referencias"


class ApiParams(str, Enum):
    """
    Mapeamento oficial dos parâmetros da API de Dados Abertos da Câmara.
    """

    DATA_INICIO = "dataInicio"
    DATA_FIM = "dataFim"
    ID_LEGISLATURA = "idLegislatura"
    ORDEM = "ordem"
    ORDENAR_POR = "ordenarPor"
    PAGINA = "pagina"
    ITENS = "itens"
    ANO = "ano"
    MES = "mes"
    SIGLA_UF = "siglaUf"
    SIGLA_PARTIDO = "siglaPartido"

    # Valores padrão da API
    ORDEM_ASC = "ASC"
    ORDEM_DESC = "DESC"


class LoadStrategy(str, Enum):
    FULL_LOAD = "full_load"
    INCREMENTAL = "incremental"


class SourceType(str, Enum):
    API = "api"
    BULK = "bulk"


class SinkType(str, Enum):
    SQLITE = "sqlite"
    DATALAKE = "datalake"


class DomainType(str, Enum):
    DEPUTADOS = "deputados"
    DESPESAS = "despesas"
    PROPOSICOES = "proposicoes"
    VOTACOES = "votacoes"
    VOTOS = "votos"
