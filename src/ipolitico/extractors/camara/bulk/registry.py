"""
URLs e metadados dos arquivos estáticos (dumps) da Câmara dos Deputados.

As URLs seguem o portal de Dados Abertos; ajuste caso o órgão altere o layout.
"""

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
    },
    "despesas": {
        "requires_year": True,
        # Padrão CEAP documentado: http://www.camara.leg.br/cotas/Ano-{ano}.csv.zip
        "url": "http://www.camara.leg.br/cotas/Ano-{year}.csv.zip",
        "bulk_granularity": "year",
        "bulk_filter_date_column": "dataDocumento",
    },
    "proposicoes": {
        "requires_year": True,
        "url": (
            "https://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes{year}.csv.zip"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "dataApresentacao",
    },
    "votacoes": {
        "requires_year": True,
        "url": (
            "https://dadosabertos.camara.leg.br/arquivos/votacoes/csv/" "votacoes-{year}.csv.zip"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": "data",
    },
    "votos": {
        "requires_year": True,
        "url": (
            "https://dadosabertos.camara.leg.br/arquivos/votacoesOrientacoes/"
            "csv/votacoesOrientacoes_{year}.csv.zip"
        ),
        "bulk_granularity": "year",
        "bulk_filter_date_column": None,
    },
}
