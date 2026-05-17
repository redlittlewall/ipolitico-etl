from enum import Enum
from typing import Dict


class LoadStrategy(str, Enum):
    """Estratégias de carga de dados gerenciadas pelo Orquestrador."""

    FULL_LOAD = "full_load"
    INCREMENTAL = "incremental"


class SourceType(str, Enum):
    """Tipos de fontes de origem dos dados suportadas pelo ETL."""

    API = "api"
    BULK = "bulk"


class SinkType(str, Enum):
    """Tipos de destinos de armazenamento (Sinks) para a persistência."""

    SQLITE = "sqlite"
    DATALAKE = "datalake"


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
    VOTOS = "votos"


class ApiParams(str, Enum):
    """Mapeamento oficial dos parâmetros e colunas da API."""

    ID = "id"
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
    DATA_DOCUMENTO = "dataDocumento"
    # Valores comuns de retorno (Ajudam nos Transformers)
    DEPUTADO_ID = "id_deputado"
    PARTIDO_NO_VOTO = "partido_no_voto"
    UF_NO_VOTO = "uf_no_voto"
    # Orquestração
    ORDEM_ASC = "ASC"
    ORDEM_DESC = "DESC"


class DomainType(str, Enum):
    """Domínios principais suportados pelo iPolitico."""

    DEPUTADOS = "deputados"
    DESPESAS = "despesas"
    PROPOSICOES = "proposicoes"
    VOTACOES = "votacoes"
    VOTOS = "votos"
    PROFISSÕES = "profissoes"
    OCUPACOES = "ocupacoes"
    ORGAOS = "orgaos"
    PARTIDOS = "partidos"
    EVENTOS = "eventos"
    BLOCOS = "blocos"
    FRENTES = "frentes"
    GRUPOS = "grupos"
    LEGISLATURAS = "legislaturas"
    DISCURSOS = "discursos"
    TRAMITACOES = "tramitacoes"
    AUTORES = "autores"
    ORIENTACOES = "orientacoes"
    ORGAOS_MEMBROS = "orgaos_membros"
    FRENTES_MEMBROS = "frentes_membros"
    RELACIONADAS = "relacionadas"
    TEMAS = "temas"


class MedallionLayer(str, Enum):
    """Camadas da Arquitetura Medallion[cite: 2]."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


class EarliestDates:
    """Datas mínimas de dados por domínio para evitar loops infinitos."""

    DEPUTADOS = "1826-04-29"
    PROPOSICOES = "1988-01-01"
    VOTACOES = "1991-01-01"
    DESPESAS = "2009-01-01"
    ORGAOS = "1946-02-01"
    PARTIDOS = "1946-02-01"
    EVENTOS = "1991-01-01"
    FRENTES = "2003-01-01"


# Facilita o acesso dinâmico: EarliestDateMap[DomainType.DESPESAS]
EARLIEST_DATE_MAP: Dict[DomainType, str] = {
    DomainType.DEPUTADOS: EarliestDates.DEPUTADOS,
    DomainType.PROPOSICOES: EarliestDates.PROPOSICOES,
    DomainType.VOTACOES: EarliestDates.VOTACOES,
    DomainType.DESPESAS: EarliestDates.DESPESAS,
    DomainType.PROFISSÕES: EarliestDates.DEPUTADOS,
    DomainType.OCUPACOES: EarliestDates.DEPUTADOS,
    DomainType.ORGAOS: EarliestDates.ORGAOS,
    DomainType.PARTIDOS: EarliestDates.PARTIDOS,
    DomainType.EVENTOS: EarliestDates.EVENTOS,
    DomainType.BLOCOS: EarliestDates.DEPUTADOS,
    DomainType.FRENTES: EarliestDates.FRENTES,
    DomainType.GRUPOS: EarliestDates.DEPUTADOS,
    DomainType.LEGISLATURAS: EarliestDates.DEPUTADOS,
    DomainType.DISCURSOS: EarliestDates.DEPUTADOS,
    DomainType.TRAMITACOES: EarliestDates.PROPOSICOES,
    DomainType.AUTORES: EarliestDates.PROPOSICOES,
    DomainType.ORIENTACOES: EarliestDates.VOTACOES,
    DomainType.ORGAOS_MEMBROS: EarliestDates.ORGAOS,
    DomainType.FRENTES_MEMBROS: EarliestDates.FRENTES,
    DomainType.RELACIONADAS: EarliestDates.PROPOSICOES,
    DomainType.TEMAS: EarliestDates.PROPOSICOES,
}
