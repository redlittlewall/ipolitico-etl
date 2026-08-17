"""
URLs e metadados dos arquivos estáticos (dumps) da Câmara dos Deputados.

Cada entrada mapeia um domínio Bulk e pode conter:

- ``requires_year``: se o dump é particionado por ano.
- ``url_template``: template de URL para download (pode conter ``{year}``).
- ``bulk_granularity``: ``"snapshot"`` ou ``"year"``.
- ``bulk_filter_date_column``: coluna usada para filtro temporal, ou ``None``.
- ``schema_overrides``: dict de nome de coluna CSV → ``pl.*`` dtype para tipagem
  na leitura (via ``pl.read_csv(schema_overrides=...)``), eliminando o segundo
  passe de cast nos transformers. Colunas de moeda BR (ex: ``vlrLiquido``) são
  mantidas como ``pl.Utf8`` e convertidas pelo helper ``convert_br_currency_columns``.
- ``rename_map``: dict opcional de nome original → nome destino para renomear
  colunas do CSV antes da transformação (ex: ``{"idOrgao": "id"}`` para que o
  ``SILVER_SCHEMAS`` que espera ``id`` funcione corretamente).

As URLs seguem o portal de Dados Abertos; ajuste caso o órgão altere o layout.
"""

import polars as pl

# Base documentada: https://dadosabertos.camara.leg.br/
BULK_REGISTRY: dict[str, dict] = {
    # NOTA: deputados não tem Bulk CSV compatível com o transformer.
    # O CSV disponível (dados cadastrais) não contém colunas políticas
    # (partido, uf, url_foto, email). Usar rota API sempre para deputados.
    "despesas": {
        "requires_year": True,
        # Padrão CEAP documentado: http://www.camara.leg.br/cotas/Ano-{ano}.csv.zip
        "url_template": "http://www.camara.leg.br/cotas/Ano-{year}.csv.zip",
        "bulk_granularity": "year",
        "bulk_filter_date_column": "dataDocumento",
        "schema_overrides": {
            "nuDeputadoId": pl.Int64,
            "ideCadastro": pl.Int64,
            "numParcela": pl.Int64,
            "numAno": pl.Int64,
            "numMes": pl.Int64,
            "ideDocumento": pl.Int64,
            # Moeda BR permanece Utf8 para processamento pelo helper de locale
            "vlrLiquido": pl.Utf8,
            "vlrDocumento": pl.Utf8,
            "vlrGlosa": pl.Utf8,
        },
    },
    "proposicoes": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes{year}.csv.zip"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "dataApresentacao",
        "schema_overrides": {"id": pl.Int64, "numero": pl.Int64, "ano": pl.Int64},
    },
    "votacoes": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/votacoes/csv/votacoes-{year}.csv.zip"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "data",
        "schema_overrides": {"aprovacao": pl.Int64},
    },
    "votos": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/votacoesOrientacoes/"
            "csv/votacoesOrientacoes_{year}.csv.zip"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": None,
        "schema_overrides": {"idDeputado": pl.Int64},
    },
    # ── Expansão: domínios institucionais com dump Bulk ────────────────────────
    "eventos": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/eventos/csv/eventos-{year}.csv"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "dataHoraInicio",
        "schema_overrides": {},
    },
    "frentes": {
        "requires_year": False,
        "url_template": "https://dadosabertos.camara.leg.br/arquivos/frentes/csv/frentes.csv",
        "bulk_granularity": "snapshot",
        "bulk_filter_date_column": None,
        "schema_overrides": {},
    },
    "grupos": {
        "requires_year": False,
        "url_template": "https://dadosabertos.camara.leg.br/arquivos/grupos/csv/grupos.csv",
        "bulk_granularity": "snapshot",
        "bulk_filter_date_column": None,
        "schema_overrides": {"idGrupo": pl.Int64},
        "rename_map": {"idGrupo": "id"},
    },
    "grupos_membros": {
        "requires_year": False,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/gruposMembros/csv/gruposMembros.csv"
        ),
        "bulk_granularity": "snapshot",
        "bulk_filter_date_column": None,
        "schema_overrides": {},
    },
    "grupos_historico": {
        "requires_year": False,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/gruposHistorico/csv/gruposHistorico.csv"
        ),
        "bulk_granularity": "snapshot",
        "bulk_filter_date_column": None,
        "schema_overrides": {},
    },
    "legislaturas": {
        "requires_year": False,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/legislaturas/csv/legislaturas.csv"
        ),
        "bulk_granularity": "snapshot",
        "bulk_filter_date_column": None,
        "schema_overrides": {},
    },
    "legislaturas_mesa": {
        "requires_year": False,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/legislaturasMesas/"
            "csv/legislaturasMesas.csv"
        ),
        "bulk_granularity": "snapshot",
        "bulk_filter_date_column": None,
        "schema_overrides": {},
    },
    # NOTA: orgaos removido do BULK_REGISTRY intencionalmente.
    # O CSV bulk de orgaos não tem coluna id numérica e o campo uri contém
    # dados corrompidos (texto legislativo em vez de URIs) devido a linhas
    # com número irregular de colunas. Usar sempre rota API para orgaos.
    "deputados_orgaos": {
        "requires_year": False,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/orgaosDeputados/csv/orgaosDeputados.csv"
        ),
        "bulk_granularity": "snapshot",
        "bulk_filter_date_column": None,
        "schema_overrides": {},
    },
    "deputados_frentes": {
        "requires_year": False,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/frentesDeputados/csv/frentesDeputados.csv"
        ),
        "bulk_granularity": "snapshot",
        "bulk_filter_date_column": None,
        "schema_overrides": {},
        "rename_map": {
            "deputado_.id": "id_deputado",
            "deputado_.idLegislatura": "idLegislatura",
        },
    },
    "ocupacoes": {
        "requires_year": False,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/deputadosOcupacoes/"
            "csv/deputadosOcupacoes.csv"
        ),
        # NOTA: bulk_granularity removida de propósito — o CSV não tem
        # id_deputado e não serve como fonte para dados por-deputado.
        # SourceRouter retorna API, não Bulk. Mantemos a URL como
        # documentação do que existe no portal Dados Abertos.
        "bulk_filter_date_column": None,
        "schema_overrides": {},
    },
    "profissoes": {
        "requires_year": False,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/deputadosProfissoes/"
            "csv/deputadosProfissoes.csv"
        ),
        # NOTA: Mesmo motivo de ocupacoes — CSV é catálogo de tipos, sem
        # id_deputado. SourceRouter retorna API.
        "bulk_filter_date_column": None,
        "schema_overrides": {},
    },
    "orientacoes": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/votacoesOrientacoes/"
            "csv/votacoesOrientacoes_{year}.csv.zip"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "dataHoraVotacao",
        "schema_overrides": {},
    },
    # ── Domínios bulk-only (Fase 3) ────────────────────────────────────────
    "funcionarios": {
        "requires_year": False,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/funcionarios/csv/funcionarios.csv"
        ),
        "bulk_granularity": "snapshot",
        "bulk_filter_date_column": None,
        "schema_overrides": {"codGrupo": pl.Int64},
        "bulk_only": True,
    },
    "tecad_categorias": {
        "requires_year": False,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/tecadCategorias/csv/tecadCategorias.csv"
        ),
        "bulk_granularity": "snapshot",
        "bulk_filter_date_column": None,
        "schema_overrides": {"codCategoria": pl.Int64, "codSubCategoria": pl.Int64},
        "bulk_only": True,
    },
    "tecad_termos": {
        "requires_year": False,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/tecadTermos/csv/tecadTermos.csv"
        ),
        "bulk_granularity": "snapshot",
        "bulk_filter_date_column": None,
        "schema_overrides": {"codTermo": pl.Int64},
        "bulk_only": True,
    },
    # ── Domínios bulk-only de eventos/votações (Fase 3) ─────────────────────────
    "eventos_presenca_deputados": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/eventosPresencaDeputados/"
            "csv/eventosPresencaDeputados-{year}.csv"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "dataHoraInicio",
        "schema_overrides": {"idEvento": pl.Int64, "idDeputado": pl.Int64},
        "bulk_only": True,
    },
    "eventos_requerimentos": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/eventosRequerimentos/"
            "csv/eventosRequerimentos-{year}.csv"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": None,
        "schema_overrides": {"idEvento": pl.Int64},
        "bulk_only": True,
    },
    "votacoes_objetos": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/votacoesObjetos/"
            "csv/votacoesObjetos-{year}.csv"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "data",
        "schema_overrides": {
            "proposicao_id": pl.Int64,
            "proposicao_codTipo": pl.Int64,
            "proposicao_numero": pl.Int64,
            "proposicao_ano": pl.Int64,
        },
        "bulk_only": True,
    },
    "votacoes_proposicoes": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/votacoesProposicoes/"
            "csv/votacoesProposicoes-{year}.csv"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "data",
        "schema_overrides": {
            "proposicao_id": pl.Int64,
            "proposicao_codTipo": pl.Int64,
            "proposicao_numero": pl.Int64,
            "proposicao_ano": pl.Int64,
        },
        "bulk_only": True,
    },
    # ── Domínios bulk-only de licitações (Fase 3) ───────────────────────────
    "licitacoes": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/licitacoes/csv/licitacoes-{year}.csv"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "dataPublicacao",
        "schema_overrides": {
            "idLicitacao": pl.Int64,
            "numero": pl.Int64,
            "ano": pl.Int64,
            "anoProcesso": pl.Int64,
            "numItens": pl.Int64,
            "numUnidades": pl.Int64,
            "numPropostas": pl.Int64,
            "numContratos": pl.Int64,
            "vlrEstimado": pl.Float64,
            "vlrContratado": pl.Float64,
            "vlrPago": pl.Float64,
        },
        "bulk_only": True,
    },
    "licitacoes_contratos": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/licitacoesContratos/csv/licitacoesContratos-{year}.csv"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "dataPublicacao",
        "schema_overrides": {
            "ano": pl.Int64,
            "idLicitacao": pl.Int64,
            "numContrato": pl.Int64,
            "anoContrato": pl.Int64,
            "vlrOriginal": pl.Float64,
            "vlrTotal": pl.Float64,
            "numSeqArquivoInstrContratual": pl.Int64,
        },
        "bulk_only": True,
    },
    "licitacoes_itens": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/licitacoesItens/csv/licitacoesItens-{year}.csv"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": None,
        "schema_overrides": {
            "ano": pl.Int64,
            "idLicitacao": pl.Int64,
            "numItem": pl.Int64,
            "numSubitem": pl.Int64,
            "qtdLicitada": pl.Float64,
            "vlrUnitarioEstimado": pl.Float64,
            "qtdContratada": pl.Float64,
            "vlrUnitarioContratado": pl.Float64,
            "vlrTotalContratado": pl.Float64,
            "numContrato": pl.Int64,
            "anoContrato": pl.Int64,
        },
        "bulk_only": True,
    },
    "licitacoes_pedidos": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/licitacoesPedidos/csv/licitacoesPedidos-{year}.csv"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "dataHoraCadastro",
        "schema_overrides": {
            "ano": pl.Int64,
            "idLicitacao": pl.Int64,
            "numPedido": pl.Int64,
            "anoPedido": pl.Int64,
            "idOrgao": pl.Int64,
        },
        "bulk_only": True,
    },
    "licitacoes_propostas": {
        "requires_year": True,
        "url_template": (
            "https://dadosabertos.camara.leg.br/arquivos/licitacoesPropostas/csv/licitacoesPropostas-{year}.csv"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "dataProposta",
        "schema_overrides": {
            "ano": pl.Int64,
            "idLicitacao": pl.Int64,
            "numItem": pl.Int64,
            "numSubitens": pl.Int64,
            "vlrEstimado": pl.Float64,
            "unidadesProposta": pl.Float64,
            "vlrProposta": pl.Float64,
            "numProposta": pl.Int64,
            "diasValidadeProposta": pl.Int64,
        },
        "bulk_only": True,
    },
    # ── Domínio mensal (issue 04) — folha de pagamento consolidada ──────────────
    # 1 arquivo CSV por ano/mês (ex: julho-de-2026-csv), ISO-8859-1, sem coluna
    # de data para filtro temporal. Nome do mês no URL sem acento ("marco", não
    # "março"). O valor anônimo por pessoa preserva Cargo = "Deputado {id}".
    "folha_pagamento": {
        "requires_year": True,
        "requires_month": True,
        "url_template": (
            "https://www2.camara.leg.br/transparencia/recursos-humanos/remuneracao/"
            "relatorios-consolidados-por-ano-e-mes/{year}/{month}-de-{year}-csv"
        ),
        "bulk_granularity": "month",
        "bulk_filter_date_column": None,
        "encoding": "latin1",
        "schema_overrides": {},
        "bulk_only": True,
    },
}
