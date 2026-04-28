from ipolitico.core.client import CamaraClient
from ipolitico.core.constants import DomainType, SourceType

# Imports da API
from ipolitico.extractors.camara.api.deputados import DeputadosExtractor
from ipolitico.extractors.camara.api.despesas import DespesasExtractor
from ipolitico.extractors.camara.api.proposicoes import ProposicoesExtractor
from ipolitico.extractors.camara.api.votacoes import VotacoesExtractor

# Imports do Bulk
from ipolitico.extractors.camara.bulk.deputados_bulk import DeputadosBulkExtractor
from ipolitico.extractors.camara.bulk.despesas_bulk import DespesasBulkExtractor
from ipolitico.extractors.camara.bulk.proposicoes_bulk import ProposicoesBulkExtractor
from ipolitico.extractors.camara.bulk.votacoes_bulk import VotacoesBulkExtractor, VotosBulkExtractor


class CamaraExtractorFactory:
    """
    Fábrica responsável por instanciar e fornecer a ferramenta correta
    (API ou Bulk) sem expor a complexidade das importações ao orquestrador.
    """

    @staticmethod
    def get_extractor(
        domain: DomainType, source: SourceType, client: CamaraClient, state_store=None
    ):
        # 1. Fluxo API (Precisa de state_store para Incremental)
        if source == SourceType.API:
            if domain == DomainType.DEPUTADOS:
                return DeputadosExtractor(client, state_store)
            elif domain == DomainType.DESPESAS:
                return DespesasExtractor(client, state_store)
            elif domain == DomainType.PROPOSICOES:
                return ProposicoesExtractor(client, state_store)
            elif domain == DomainType.VOTACOES:
                return VotacoesExtractor(client, state_store)

        # 2. Fluxo Bulk (Dumps estáticos)
        elif source == SourceType.BULK:
            if domain == DomainType.DEPUTADOS:
                return DeputadosBulkExtractor(client)
            if domain == DomainType.DESPESAS:
                return DespesasBulkExtractor(client)
            if domain == DomainType.PROPOSICOES:
                return ProposicoesBulkExtractor(client)
            if domain == DomainType.VOTACOES:
                return VotacoesBulkExtractor(client)
            if domain == DomainType.VOTOS:
                return VotosBulkExtractor(client)

        raise ValueError(f"Extrator não suportado: domain={domain.value}, source={source.value}")
