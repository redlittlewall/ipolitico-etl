"""
Central registry of URLs for Static Dumps (Bulk) from the Chamber of Deputies.
Decouples network infrastructure from the business rule of endpoint mapping.
"""

from typing import Dict, Union

# Define a tipagem estrita para o dicionário de rotas Bulk
BULK_REGISTRY: Dict[str, Dict[str, Union[str, bool]]] = {
    "deputados": {
        "url": "https://dadosabertos.camara.leg.br/arquivos/deputados/csv/deputados.csv",
        "requires_year": False,
    },
    "deputados_profissoes": {
        "url": "https://dadosabertos.camara.leg.br/arquivos/deputadosProfissoes/csv/deputadosProfissoes.csv",
        "requires_year": False,
    },
    "deputados_ocupacoes": {
        "url": "https://dadosabertos.camara.leg.br/arquivos/deputadosOcupacoes/csv/deputadosOcupacoes.csv",
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
