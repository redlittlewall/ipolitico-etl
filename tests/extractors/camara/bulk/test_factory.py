from unittest.mock import MagicMock

import pytest
from ipolitico.core.constants import DomainType, SourceType

# API Extractors
from ipolitico.extractors.camara.api.deputados import DeputadosExtractor
from ipolitico.extractors.camara.api.despesas import DespesasExtractor
from ipolitico.extractors.camara.api.proposicoes import ProposicoesExtractor
from ipolitico.extractors.camara.api.votacoes import VotacoesExtractor

# Bulk Extractors
from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor
from ipolitico.extractors.camara.bulk.factory import CamaraExtractorFactory


def test_factory_api_routing():
    """
    [BLINDAGEM ESTRUTURAL] Garante que a Factory instancia corretamente
    todas as rotas do tipo API e repassa o State Store.
    """
    client = MagicMock()
    state_store = MagicMock()

    # Testa o mapeamento de todos os domínios da API
    assert isinstance(
        CamaraExtractorFactory.get_extractor(
            DomainType.DEPUTADOS, SourceType.API, client, state_store
        ),
        DeputadosExtractor,
    )
    assert isinstance(
        CamaraExtractorFactory.get_extractor(
            DomainType.DESPESAS, SourceType.API, client, state_store
        ),
        DespesasExtractor,
    )
    assert isinstance(
        CamaraExtractorFactory.get_extractor(
            DomainType.PROPOSICOES, SourceType.API, client, state_store
        ),
        ProposicoesExtractor,
    )
    assert isinstance(
        CamaraExtractorFactory.get_extractor(
            DomainType.VOTACOES, SourceType.API, client, state_store
        ),
        VotacoesExtractor,
    )


def test_factory_bulk_routing():
    """
    [BLINDAGEM ESTRUTURAL] Garante que a Factory instancia corretamente
    as rotas Bulk (que não precisam de State Store).
    """
    client = MagicMock()

    # Testa o mapeamento de todos os domínios Bulk
    for dom in [
        DomainType.DEPUTADOS,
        DomainType.DESPESAS,
        DomainType.PROPOSICOES,
        DomainType.VOTACOES,
        DomainType.VOTOS,
        # Expansão
        DomainType.EVENTOS,
        DomainType.FRENTES,
        DomainType.GRUPOS,
        DomainType.GRUPOS_MEMBROS,
        DomainType.GRUPOS_HISTORICO,
        DomainType.LEGISLATURAS,
        DomainType.LEGISLATURAS_MESA,
        DomainType.ORGAOS,
        DomainType.DEPUTADOS_ORGAOS,
        DomainType.DEPUTADOS_FRENTES,
        DomainType.OCUPACOES,
        DomainType.PROFISSÕES,
        DomainType.ORIENTACOES,
    ]:
        assert isinstance(
            CamaraExtractorFactory.get_extractor(dom, SourceType.BULK, client),
            BaseBulkExtractor,
        )


def test_factory_unsupported_routing():
    """
    [FAIL-FAST] Garante que se o desenvolvedor tentar rotear algo que
    não existe, a Factory trava o pipeline imediatamente.
    """
    client = MagicMock()

    # Criamos um Mock que finge ser um Enum inválido
    class DummyEnum:
        def __init__(self, value):
            self.value = value

    with pytest.raises(ValueError, match="Extrator não suportado"):
        CamaraExtractorFactory.get_extractor(
            DummyEnum("dominio_falso"), DummyEnum("fonte_falsa"), client
        )
