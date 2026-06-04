"""
URLs e metadados dos arquivos estáticos (dumps) da Câmara dos Deputados.

Cada entrada mapeia um domínio Bulk e pode conter:

- ``requires_year``: se o dump é particionado por ano.
- ``url``: template de URL para download (pode conter ``{year}``).
- ``bulk_granularity``: ``"snapshot"`` ou ``"year"``.
- ``bulk_filter_date_column``: coluna usada para filtro temporal, ou ``None``.
- ``schema_overrides``: dict de nome de coluna CSV → ``pl.*`` dtype para tipagem
  na leitura (via ``pl.read_csv(schema_overrides=...)``), eliminando o segundo
  passe de cast nos transformers. Colunas de moeda BR (ex: ``vlrLiquido``) são
  mantidas como ``pl.Utf8`` e convertidas pelo helper ``convert_br_currency_columns``.

As URLs seguem o portal de Dados Abertos; ajuste caso o órgão altere o layout.
"""

import polars as pl

# Base documentada: https://dadosabertos.camara.leg.br/
BULK_REGISTRY: dict[str, dict] = {
    "deputados": {
        "requires_year": False,
        "url": (
            "https://dadosabertos.camara.leg.br/arquivos/deputados/cadastroDeputadosLegislaturaAtual/"
            "cadastro_Deputados_legislatura_inicial_-fim_-na_legislatura_atual.csv"
        ),
        "bulk_granularity": "snapshot",
        "bulk_filter_date_column": None,
        "schema_overrides": {"Id": pl.Int64, "idLegislatura": pl.Int64},
    },
    "despesas": {
        "requires_year": True,
        # Padrão CEAP documentado: http://www.camara.leg.br/cotas/Ano-{ano}.csv.zip
        "url": "http://www.camara.leg.br/cotas/Ano-{year}.csv.zip",
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
        "url": (
            "https://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes{year}.csv.zip"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "dataApresentacao",
        "schema_overrides": {"id": pl.Int64, "numero": pl.Int64, "ano": pl.Int64},
    },
    "votacoes": {
        "requires_year": True,
        "url": (
            "https://dadosabertos.camara.leg.br/arquivos/votacoes/csv/" "votacoes-{year}.csv.zip"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "data",
        "schema_overrides": {"aprovacao": pl.Int64},
    },
    "votos": {
        "requires_year": True,
        "url": (
            "https://dadosabertos.camara.leg.br/arquivos/votacoesOrientacoes/"
            "csv/votacoesOrientacoes_{year}.csv.zip"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": None,
        "schema_overrides": {"idDeputado": pl.Int64},
    },
}
