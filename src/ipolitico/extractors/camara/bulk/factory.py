from ipolitico.core.client import CamaraClient

# Imports da API (Assumindo que você moveu eles para a pasta api/)
from ipolitico.extractors.camara.api.deputados import DeputadosExtractor
from ipolitico.extractors.camara.api.despesas import DespesasExtractor
from ipolitico.extractors.camara.api.proposicoes import ProposicoesExtractor
from ipolitico.extractors.camara.api.votacoes import VotacoesExtractor

# Imports do Bulk
from ipolitico.extractors.camara.bulk.deputados_bulk import DeputadosBulkExtractor
from ipolitico.extractors.camara.bulk.despesas_bulk import DespesasBulkExtractor
from ipolitico.extractors.camara.bulk.proposicoes_bulk import ProposicoesBulkExtractor
from ipolitico.extractors.camara.bulk.votacoes_bulk import VotacoesBulkExtractor


class CamaraExtractorFactory:
    """
    Fábrica responsável por instanciar e fornecer a ferramenta correta
    (API ou Bulk) sem expor a complexidade das importações ao orquestrador.
    """

    @staticmethod
    def get_extractor(domain: str, source: str, client: CamaraClient, state_store=None):
        # 1. Fluxo API (Precisa de state_store para Incremental)
        if source == "api":
            if domain == "deputados":
                return DeputadosExtractor(client, state_store)
            elif domain == "despesas":
                return DespesasExtractor(client, state_store)
            elif domain == "proposicoes":
                return ProposicoesExtractor(client, state_store)
            elif domain == "votacoes":
                return VotacoesExtractor(client, state_store)

        # 2. Fluxo Bulk (Dumps estáticos)
        elif source == "bulk":
            if domain == "deputados":
                return DeputadosBulkExtractor(client)
            if domain == "despesas":
                return DespesasBulkExtractor(client)
            if domain == "proposicoes":
                return ProposicoesBulkExtractor(client)
            if domain in ("votacoes", "votos"):
                return VotacoesBulkExtractor(client)

        raise ValueError(f"Extrator não suportado: domain={domain}, source={source}")
