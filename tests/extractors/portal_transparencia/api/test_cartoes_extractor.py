"""Testes do PortalCartoesApiExtractor — rota de consulta pontual (ticket 04).

ROTA DUPLA: em INCREMENTAL (janela ≤ 12 meses), o domínio cg_cartoes usa a
consulta pontual da API v3 ``/api-de-dados/cartoes`` em BLOCOS MENSAIS — o job
``{"year", "month"}`` (``MonthlyBulkStrategy``) vira o filtro
``mesExtratoInicio``/``mesExtratoFim`` do mês (1 mês ≤ 12 ✓). A API exige ≥1
filtro (pagina sozinho → 400 real) — sem janela, o extrator levanta ValueError
antes de paginar a falha.
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.core.config import PORTAL_API_BASE_URL
from ipolitico.extractors.portal_transparencia.api.cartoes_extractor import (
    PortalCartoesApiExtractor,
)

API_BASE = PORTAL_API_BASE_URL.rstrip("/")
ENDPOINT = "api-de-dados/cartoes"


@pytest.fixture
def mock_client():
    """Cliente com ``fetch`` mockado (a API v3 retorna lista top-level)."""
    client = AsyncMock()
    client.BASE_URL = PORTAL_API_BASE_URL
    return client


def _row(i: int) -> dict:
    """Uma transação como a API devolve (tipoCartao int, valor string)."""
    return {
        "id": i,
        "mesExtrato": "06/2026",
        "dataTransacao": "15/06/2026",
        "valorTransacao": "250,34",
        "tipoCartao": 1,
        "estabelecimento": {"id": i, "nome": f"ESTABELECIMENTO {i}"},
        "unidadeGestora": {
            "codigo": "17000",
            "nome": "UG X",
            "orgaoVinculado": {"codigoSIAFI": "17000", "sigla": "X", "nome": "ORGAO X"},
            "orgaoMaximo": {"codigo": "17000", "sigla": "X", "nome": "ORGAO MAX X"},
        },
        "portador": {"cpfFormatado": "123.456.789-00", "nome": "PORTADOR A"},
    }


def test_endpoint_constante():
    """O extrator aponta para o endpoint real de cartões na API v3."""
    assert PortalCartoesApiExtractor.ENDPOINT == ENDPOINT


@pytest.mark.asyncio
async def test_extract_year_month_vira_filtro_mensal(mock_client):
    """``(year, month)`` → mesExtratoInicio/Fim do mês (1 mês ≤ 12 meses ✓)."""
    captured: dict = {}

    async def fake_fetch(endpoint, params=None):
        captured["params"] = params
        return [_row(1)] if (params or {}).get("pagina", 1) == 1 else []

    mock_client.fetch.side_effect = fake_fetch
    ext = PortalCartoesApiExtractor(mock_client)

    result = await ext.extract(year=2026, month=6)

    assert captured["params"]["mesExtratoInicio"] == "06/2026"
    assert captured["params"]["mesExtratoFim"] == "06/2026"
    assert result.height == 1
    # _source_url replayável até a página, com o filtro de mês no query string
    assert result["_source_url"].to_list() == [
        f"{API_BASE}/{ENDPOINT}?mesExtratoFim=06/2026&mesExtratoInicio=06/2026&pagina=1"
    ]


@pytest.mark.asyncio
async def test_extract_mes_sem_zero_a_esquerda(mock_client):
    """``month=6`` vira "06/2026" no filtro (formato MM/AAAA da API)."""
    captured: dict = {}

    async def fake_fetch(endpoint, params=None):
        captured["params"] = params
        return []

    mock_client.fetch.side_effect = fake_fetch
    ext = PortalCartoesApiExtractor(mock_client)

    await ext.extract(year=2026, month=11)

    assert captured["params"]["mesExtratoInicio"] == "11/2026"
    assert captured["params"]["mesExtratoFim"] == "11/2026"


@pytest.mark.asyncio
async def test_extract_sem_janela_levanta_valueerror(mock_client):
    """Sem year/month → ValueError ANTES de chamar a API (400 real sem filtro)."""
    mock_client.fetch.return_value = []
    ext = PortalCartoesApiExtractor(mock_client)

    with pytest.raises(ValueError):
        await ext.extract()
    with pytest.raises(ValueError):
        await ext.extract(year=2026)
    with pytest.raises(ValueError):
        await ext.extract(month=6)
    assert mock_client.fetch.await_count == 0  # nunca paginou a falha


@pytest.mark.asyncio
async def test_extract_pagina_todas_as_paginas(mock_client):
    """Percorre páginas até a final curta dentro do bloco mensal."""
    page1 = [_row(i) for i in range(1, 16)]
    page2 = [_row(i) for i in range(16, 21)]

    async def fake_fetch(endpoint, params=None):
        page = (params or {}).get("pagina", 1)
        return page1 if page == 1 else page2

    mock_client.fetch.side_effect = fake_fetch
    ext = PortalCartoesApiExtractor(mock_client)

    result = await ext.extract(year=2026, month=6)

    assert result.height == 20
    assert result["id"].to_list() == list(range(1, 21))
    assert (
        result["_source_url"].to_list()
        == [f"{API_BASE}/{ENDPOINT}?mesExtratoFim=06/2026&mesExtratoInicio=06/2026&pagina=1"] * 15
        + [f"{API_BASE}/{ENDPOINT}?mesExtratoFim=06/2026&mesExtratoInicio=06/2026&pagina=2"] * 5
    )


@pytest.mark.asyncio
async def test_construtor_aceita_modules_ignorado(mock_client):
    """Kwarg compartilhado do YAML (bulk) é aceito e ignorado na rota API."""
    ext = PortalCartoesApiExtractor(mock_client, modules=["cpgf", "cpcc", "cpdc"])
    assert ext.ENDPOINT == ENDPOINT
