"""Testes do PortalEmendasApiExtractor — cg_emendas por ano (ticket 04).

Fonte real da validação do ticket 04: API v3 ``/api-de-dados/emendas`` com o
filtro ``ano`` — "respeita a janela da API por ano". O job anual chega como
``{"ano": y}`` (mapper da ``AnnualWindowStrategy``) → ``extract(ano=...)``.
Sem ``ano``, o walk é livre (``pagina`` sozinho também é aceito pela API).
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.core.config import PORTAL_API_BASE_URL
from ipolitico.extractors.portal_transparencia.api.emendas_extractor import (
    PortalEmendasApiExtractor,
)

API_BASE = PORTAL_API_BASE_URL.rstrip("/")
ENDPOINT = "api-de-dados/emendas"


@pytest.fixture
def mock_client():
    """Cliente com ``fetch`` mockado (a API v3 retorna lista top-level)."""
    client = AsyncMock()
    client.BASE_URL = PORTAL_API_BASE_URL
    return client


def _row(ano: int, i: int) -> dict:
    """Uma emenda como a API devolve (valor* como string vírgula-decimal)."""
    return {
        "codigoEmenda": f"{ano}3000{i:04d}",
        "ano": ano,
        "tipoEmenda": "Individual",
        "autor": "DEPUTADO",
        "nomeAutor": f"NOME {i}",
        "numeroEmenda": str(i),
        "localidadeDoGasto": "BRASILIA",
        "funcao": "SAUDE",
        "subfuncao": "ATENCAO BASICA",
        "valorEmpenhado": "R$ 1.234,56",
        "valorLiquidado": "R$ 1.000,00",
        "valorPago": "R$ 950,00",
        "valorRestoInscrito": "R$ 0,00",
        "valorRestoCancelado": "R$ 0,00",
        "valorRestoPago": "R$ 0,00",
    }


def test_endpoint_constante():
    """O extrator aponta para o endpoint real de emendas na API v3."""
    assert PortalEmendasApiExtractor.ENDPOINT == ENDPOINT


@pytest.mark.asyncio
async def test_extract_ano_vira_param(mock_client):
    """``ano`` do job (mapper AnnualWindowStrategy) vira o filtro da API."""
    captured: dict = {}

    async def fake_fetch(endpoint, params=None):
        captured["params"] = params
        return [_row(2026, 1)] if (params or {}).get("pagina", 1) == 1 else []

    mock_client.fetch.side_effect = fake_fetch
    ext = PortalEmendasApiExtractor(mock_client)

    result = await ext.extract(ano=2026)

    assert captured["params"]["ano"] == 2026
    assert result.height == 1
    # _source_url replayável até a página, com o filtro do ano no query string
    assert result["_source_url"].to_list() == [f"{API_BASE}/{ENDPOINT}?ano=2026&pagina=1"]


@pytest.mark.asyncio
async def test_extract_sem_ano_walk_livre(mock_client):
    """Sem ``ano``: pagina sozinho basta (coleção inteira)."""
    fetched_pages: list[dict] = []

    async def fake_fetch(endpoint, params=None):
        fetched_pages.append(dict(params or {}))
        page = (params or {}).get("pagina", 1)
        return [_row(2026, 1)] if page == 1 else []

    mock_client.fetch.side_effect = fake_fetch
    ext = PortalEmendasApiExtractor(mock_client)

    result = await ext.extract()

    assert len(fetched_pages) >= 1
    # params só com pagina (sem ano)
    assert all("ano" not in p for p in fetched_pages)
    assert result["_source_url"].to_list() == [f"{API_BASE}/{ENDPOINT}?pagina=1"]


@pytest.mark.asyncio
async def test_extract_pagina_todas_as_paginas(mock_client):
    """Percorre páginas até a final curta, acumulando com o filtro de ano."""
    page1 = [_row(2025, i) for i in range(1, 16)]
    page2 = [_row(2025, i) for i in range(16, 26)]

    async def fake_fetch(endpoint, params=None):
        page = (params or {}).get("pagina", 1)
        return page1 if page == 1 else page2

    mock_client.fetch.side_effect = fake_fetch
    ext = PortalEmendasApiExtractor(mock_client)

    result = await ext.extract(ano=2025)

    assert result.height == 25
    assert result["ano"].to_list() == [2025] * 25
    assert (
        result["_source_url"].to_list()
        == [f"{API_BASE}/{ENDPOINT}?ano=2025&pagina=1"] * 15
        + [f"{API_BASE}/{ENDPOINT}?ano=2025&pagina=2"] * 10
    )


@pytest.mark.asyncio
async def test_extract_api_vazia_retorna_vazio(mock_client):
    """Ano sem emendas (página vazia) → DataFrame vazio, sem crash."""
    mock_client.fetch.return_value = []
    ext = PortalEmendasApiExtractor(mock_client)

    result = await ext.extract(ano=1990)

    assert result.is_empty()
