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
    DEPUTADOS_FRENTES = "deputados_frentes"
    DEPUTADOS_ORGAOS = "deputados_orgaos"
    DEPUTADOS_EVENTOS = "deputados_eventos"
    DEPUTADOS_HISTORICO = "deputados_historico"
    MANDATOS_EXTERNOS = "mandatos_externos"
    EVENTOS_DEPUTADOS = "eventos_deputados"
    EVENTOS_VOTACOES = "eventos_votacoes"
    EVENTOS_PAUTA = "eventos_pauta"
    PARTIDOS_MEMBROS = "partidos_membros"
    PARTIDOS_LIDERES = "partidos_lideres"
    PROPOSICOES_VOTACOES = "proposicoes_votacoes"
    BLOCOS_PARTIDOS = "blocos_partidos"
    REFERENCIAS = "referencias"
    DEPUTADOS_DETALHE = "deputados_detalhe"
    ORGAOS_DETALHE = "orgaos_detalhe"
    EVENTOS_DETALHE = "eventos_detalhe"
    VOTACOES_DETALHE = "votacoes_detalhe"
    FRENTES_DETALHE = "frentes_detalhe"
    PARTIDOS_DETALHE = "partidos_detalhe"
    GRUPOS_DETALHE = "grupos_detalhe"
    LEGISLATURAS_DETALHE = "legislaturas_detalhe"
    BLOCOS_DETALHE = "blocos_detalhe"
    PROPOSICOES_DETALHE = "proposicoes_detalhe"
    EVENTOS_ORGAOS = "eventos_orgaos"
    ORGAOS_EVENTOS = "orgaos_eventos"
    ORGAOS_VOTACOES = "orgaos_votacoes"
    GRUPOS_MEMBROS = "grupos_membros"
    GRUPOS_HISTORICO = "grupos_historico"
    LEGISLATURAS_LIDERES = "legislaturas_lideres"
    LEGISLATURAS_MESA = "legislaturas_mesa"
    # Domínios bulk-only (sem rota API REST)
    FUNCIONARIOS = "funcionarios"
    TECAD_CATEGORIAS = "tecad_categorias"
    TECAD_TERMOS = "tecad_termos"
    # Domínios bulk-only de licitações (dumps CSV anuais)
    LICITACOES = "licitacoes"
    LICITACOES_CONTRATOS = "licitacoes_contratos"
    LICITACOES_ITENS = "licitacoes_itens"
    LICITACOES_PEDIDOS = "licitacoes_pedidos"
    LICITACOES_PROPOSTAS = "licitacoes_propostas"


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
    FUNCIONARIOS = "1826-04-29"
    TECAD_CATEGORIAS = "1826-04-29"
    TECAD_TERMOS = "1826-04-29"
    LICITACOES = "1999-01-01"


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
    DomainType.DEPUTADOS_FRENTES: EarliestDates.DEPUTADOS,
    DomainType.DEPUTADOS_ORGAOS: EarliestDates.DEPUTADOS,
    DomainType.DEPUTADOS_EVENTOS: EarliestDates.DEPUTADOS,
    DomainType.DEPUTADOS_HISTORICO: EarliestDates.DEPUTADOS,
    DomainType.MANDATOS_EXTERNOS: EarliestDates.DEPUTADOS,
    DomainType.EVENTOS_DEPUTADOS: EarliestDates.EVENTOS,
    DomainType.EVENTOS_VOTACOES: EarliestDates.EVENTOS,
    DomainType.EVENTOS_PAUTA: EarliestDates.EVENTOS,
    DomainType.PARTIDOS_MEMBROS: EarliestDates.PARTIDOS,
    DomainType.PARTIDOS_LIDERES: EarliestDates.PARTIDOS,
    DomainType.PROPOSICOES_VOTACOES: EarliestDates.PROPOSICOES,
    DomainType.BLOCOS_PARTIDOS: EarliestDates.DEPUTADOS,
    DomainType.REFERENCIAS: EarliestDates.DEPUTADOS,
    DomainType.DEPUTADOS_DETALHE: EarliestDates.DEPUTADOS,
    DomainType.ORGAOS_DETALHE: EarliestDates.ORGAOS,
    DomainType.EVENTOS_DETALHE: EarliestDates.EVENTOS,
    DomainType.VOTACOES_DETALHE: EarliestDates.VOTACOES,
    DomainType.FRENTES_DETALHE: EarliestDates.FRENTES,
    DomainType.PARTIDOS_DETALHE: EarliestDates.PARTIDOS,
    DomainType.GRUPOS_DETALHE: EarliestDates.DEPUTADOS,
    DomainType.LEGISLATURAS_DETALHE: EarliestDates.DEPUTADOS,
    DomainType.BLOCOS_DETALHE: EarliestDates.DEPUTADOS,
    DomainType.PROPOSICOES_DETALHE: EarliestDates.PROPOSICOES,
    DomainType.EVENTOS_ORGAOS: EarliestDates.EVENTOS,
    DomainType.ORGAOS_EVENTOS: EarliestDates.ORGAOS,
    DomainType.ORGAOS_VOTACOES: EarliestDates.ORGAOS,
    DomainType.GRUPOS_MEMBROS: EarliestDates.DEPUTADOS,
    DomainType.GRUPOS_HISTORICO: EarliestDates.DEPUTADOS,
    DomainType.LEGISLATURAS_LIDERES: EarliestDates.DEPUTADOS,
    DomainType.LEGISLATURAS_MESA: EarliestDates.DEPUTADOS,
    # Domínios bulk-only
    DomainType.FUNCIONARIOS: EarliestDates.FUNCIONARIOS,
    DomainType.TECAD_CATEGORIAS: EarliestDates.TECAD_CATEGORIAS,
    DomainType.TECAD_TERMOS: EarliestDates.TECAD_TERMOS,
    # Domínios bulk-only de licitações
    DomainType.LICITACOES: EarliestDates.LICITACOES,
    DomainType.LICITACOES_CONTRATOS: EarliestDates.LICITACOES,
    DomainType.LICITACOES_ITENS: EarliestDates.LICITACOES,
    DomainType.LICITACOES_PEDIDOS: EarliestDates.LICITACOES,
    DomainType.LICITACOES_PROPOSTAS: EarliestDates.LICITACOES,
}
