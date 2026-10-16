"""Testes do PortalImoveisFuncionaisApiExtractor — cg_imoveis_funcionais (ticket 04).

Correção de fonte da validação real do ticket 04: o dump bulk
``/download-de-dados/imoveis-funcionais`` está INDISPONÍVEL (403 AccessDenied
do S3) → fonte única é a API v3 ``/api-de-dados/imoveis``, que NÃO exige filtro
(walk livre com ``pagina``). O raw preserva os objetos aninhados
(``orgaoResponsavel``/``situacao``/``regiao``) — o achatamento vive no
transformer (padrão do teste de orgaos: extrator devolve o shape como veio).
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.core.config import PORTAL_API_BASE_URL
from ipolitico.extractors.portal_transparencia.api.imoveis_extractor import (
    PortalImoveisFuncionaisApiExtractor,
)

API_BASE = PORTAL_API_BASE_URL.rstrip("/")
ENDPOINT = "api-de-dados/imoveis"


@pytest.fixture
def mock_client():
    """Cliente com ``fetch`` mockado (a API v3 retorna lista top-level)."""
    client = AsyncMock()
    client.BASE_URL = PORTAL_API_BASE_URL
    return client


def _row(i: int) -> dict:
    """Uma linha bruta como a API v3 devolve (objetos aninhados preservados)."""
    return {
        "id": i,
        "dataReferencia": "30/06/2026",
        "orgaoResponsavel": {"codigoSIAFI": "17000", "nome": "MINISTERIO X"},
        "situacao": {"id": 1, "descricao": "Próprio"},
        "regiao": {"id": 2, "descricao": "NORDESTE"},
        "endereco": f"ENDERECO {i}",
        "cep": "70000-000",
    }


def test_endpoint_constante():
    """O extrator aponta para o endpoint real de imóveis na API v3."""
    assert PortalImoveisFuncionaisApiExtractor.ENDPOINT == ENDPOINT


@pytest.mark.asyncio
async def test_extract_walk_livre_pagina_todas(mock_client):
    """Sem filtro: pagina sozinho basta; percorre até a página final curta."""
    page1 = [_row(i) for i in range(1, 16)]
    page2 = [_row(i) for i in range(16, 21)]

    async def fake_fetch(endpoint, params=None):
        assert endpoint == ENDPOINT
        page = (params or {}).get("pagina", 1)
        assert set(params) == {"pagina"}  # walk livre, sem filtro adicional
        return page1 if page == 1 else page2

    mock_client.fetch.side_effect = fake_fetch
    ext = PortalImoveisFuncionaisApiExtractor(mock_client)

    result = await ext.extract()

    assert result.height == 20
    assert result["id"].to_list() == list(range(1, 21))
    assert (
        result["_source_url"].to_list()
        == [f"{API_BASE}/{ENDPOINT}?pagina=1"] * 15 + [f"{API_BASE}/{ENDPOINT}?pagina=2"] * 5
    )


@pytest.mark.asyncio
async def test_extract_preserva_structs_aninhadas(mock_client):
    """O raw mantém orgaoResponsavel/situacao/regiao como structs (transform er acha)."""

    async def fake_fetch(endpoint, params=None):
        page = (params or {}).get("pagina", 1)
        return [_row(1)] if page == 1 else []

    mock_client.fetch.side_effect = fake_fetch
    ext = PortalImoveisFuncionaisApiExtractor(mock_client)

    result = await ext.extract()

    orgao = result["orgaoResponsavel"].to_list()[0]
    assert orgao["nome"] == "MINISTERIO X"
    assert orgao["codigoSIAFI"] == "17000"
    situacao = result["situacao"].to_list()[0]
    assert situacao["id"] == 1
    assert situacao["descricao"] == "Próprio"
    regiao = result["regiao"].to_list()[0]
    assert regiao["id"] == 2
    assert regiao["descricao"] == "NORDESTE"


@pytest.mark.asyncio
async def test_extract_api_vazia_retorna_vazio(mock_client):
    """API sem dados (lista vazia) → DataFrame vazio, sem crash."""
    mock_client.fetch.return_value = []
    ext = PortalImoveisFuncionaisApiExtractor(mock_client)

    result = await ext.extract()

    assert result.is_empty()
