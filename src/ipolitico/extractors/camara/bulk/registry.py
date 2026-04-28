"""
Registro central de URLs para Dumps Estáticos (Bulk) da Câmara dos Deputados.
Desacopla a infraestrutura de rede da regra de negócio de mapeamento de endpoints.
"""

BULK_REGISTRY = {
    "deputados": {
        "url": "https://dadosabertos.camara.leg.br/arquivos/deputados/csv/deputados.csv",
        "requires_year": False,
    },
    "despesas": {
        "url": "https://www.camara.leg.br/cotas/Ano-{year}.csv.zip",
        "requires_year": True,
    },
    "proposicoes": {
        "url": "https://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes-{year}.csv",
        "requires_year": True,
    },
    "votacoes": {
        "url": "https://dadosabertos.camara.leg.br/arquivos/votacoes/csv/votacoes-{year}.csv",
        "requires_year": True,
    },
    "votos": {
        "url": "https://dadosabertos.camara.leg.br/arquivos/votacoesVotos/csv/votacoesVotos-{year}.csv",
        "requires_year": True,
    },
}
