"""Testes do PortalOrgaosApiExtractor — cg_orgaos via API v3 (ticket 02).

Correção de fonte descoberta na validação real do ticket 02: o portal NÃO tem
módulo bulk ``/download-de-dados/orgaos`` (o serviço responde HTTP 500 para
módulo inexistente, enquanto ``servidores``/``viagens`` respondem 200). A fonte
real de órgãos SIAPE é a API v3 ``/api-de-dados/orgaos-siape`` (640 registros,
contrato ``codigo``/``descricao``, page_size fixo em 15 pela API).
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.core.config import PORTAL_API_BASE_URL
from ipolitico.extractors.portal_transparencia.api.orgaos_extractor import (
    PortalOrgaosApiExtractor,
)

API_BASE = PORTAL_API_BASE_URL.rstrip("/")
ENDPOINT = "api-de-dados/orgaos-siape"


@pytest.fixture
def mock_client():
    """Cliente com ``fetch`` mockado (a API v3 retorna lista top-level)."""
    client = AsyncMock()
    client.BASE_URL = PORTAL_API_BASE_URL
    return client


def _row(codigo: str, descricao: str) -> dict:
    """Uma linha bruta como a API devolve (codigo com zeros à esquerda)."""
    return {"codigo": codigo, "descricao": descricao}


def test_endpoint_constante():
    """O extrator aponta para o endpoint real de órgãos SIAPE na API v3."""
    assert PortalOrgaosApiExtractor.ENDPOINT == ENDPOINT


@pytest.mark.asyncio
async def test_extract_pagina_todas_as_paginas(mock_client):
    """Percorre páginas até a última (curta): 15 + 10 = 25 registros."""
    page1 = [_row(f"{i:05d}", f"ORGAO {i}") for i in range(1, 16)]
    page2 = [_row(f"{i:05d}", f"ORGAO {i}") for i in range(16, 26)]

    async def fake_fetch(endpoint, params=None):
        assert endpoint == ENDPOINT
        page = (params or {}).get("pagina", 1)
        return page1 if page == 1 else page2

    mock_client.fetch.side_effect = fake_fetch
    ext = PortalOrgaosApiExtractor(mock_client)

    result = await ext.extract()

    assert result.height == 25
    assert result["codigo"].to_list() == [f"{i:05d}" for i in range(1, 26)]
    assert result["_source_url"].to_list() == [
        f"{API_BASE}/{ENDPOINT}?pagina=1"
    ] * 15 + [f"{API_BASE}/{ENDPOINT}?pagina=2"] * 10


@pytest.mark.asyncio
async def test_extract_api_vazia_retorna_vazio(mock_client):
    """API sem dados (404/lista vazia) → DataFrame vazio, sem crash."""
    mock_client.fetch.return_value = []
    ext = PortalOrgaosApiExtractor(mock_client)

    result = await ext.extract()

    assert result.is_empty()


@pytest.mark.asyncio
async def test_extract_codigo_permite_zero_a_esquerda(mock_client):
    """``codigo`` permanece String no raw (``00001`` não vira 1)."""
    async def fake_fetch(endpoint, params=None):
        page = (params or {}).get("pagina", 1)
        return [_row("00001", "IGNORADO - CONVERSAO DO SIPEFAZ")] if page == 1 else []

    mock_client.fetch.side_effect = fake_fetch
    ext = PortalOrgaosApiExtractor(mock_client)

    result = await ext.extract()

    assert result["codigo"].to_list() == ["00001"]
    assert result["descricao"].to_list() == ["IGNORADO - CONVERSAO DO SIPEFAZ"]


@pytest.mark.asyncio
async def test_extract_pagina_unica_quando_curta(mock_client):
    """Página 1 curta → 1 registro; página seguinte vazia encerra a iteração.

    O page_size é derivado da primeira página; uma página curta não prova que é
    a última, então o loop pede a página seguinte (vazia na API real) e para.
    """
    async def fake_fetch(endpoint, params=None):
        page = (params or {}).get("pagina", 1)
        return [_row("13200", "MINISTERIO DA FAZENDA")] if page == 1 else []

    mock_client.fetch.side_effect = fake_fetch
    ext = PortalOrgaosApiExtractor(mock_client)

    result = await ext.extract()

    assert result.height == 1
    assert mock_client.fetch.await_count == 2
    assert result["_source_url"].to_list() == [f"{API_BASE}/{ENDPOINT}?pagina=1"]
