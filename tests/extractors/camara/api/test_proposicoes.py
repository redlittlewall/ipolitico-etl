"""Testes do ProposicoesExtractor (API)."""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.camara.api.proposicao_child import TramitacoesExtractor
from ipolitico.extractors.camara.api.proposicoes import ProposicoesExtractor


@pytest.fixture
def extractor() -> ProposicoesExtractor:
    client = AsyncMock()
    ext = ProposicoesExtractor(client)
    ext.fetch_paginated = AsyncMock()
    return ext


@pytest.mark.asyncio
async def test_extract_passes_year_and_dates(extractor: ProposicoesExtractor):
    extractor.fetch_paginated.return_value = [{"id": 1}]

    df = await extractor.extract(start_date="2026-04-01", end_date="2026-04-30", year=2026)

    assert df.height == 1
    _route, params = extractor.fetch_paginated.call_args[0]
    assert params.get("ano") == 2026
    assert params["dataInicio"] == "2026-04-01"
    assert params["dataFim"] == "2026-04-30"


@pytest.mark.asyncio
async def test_extract_empty_returns_empty(extractor: ProposicoesExtractor):
    extractor.fetch_paginated.return_value = []

    df = await extractor.extract(start_date="2026-01-01", end_date="2026-01-31", year=2026)

    assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_injects_source_url(extractor: ProposicoesExtractor):
    """Cada registro deve ter _source_url apontando para /proposicoes/{id}."""
    extractor.fetch_paginated.return_value = [
        {"id": 100, "siglaTipo": "PL", "numero": 123},
        {"id": 200, "siglaTipo": "PEC", "numero": 45},
    ]

    df = await extractor.extract(start_date="2026-01-01", end_date="2026-12-31")

    assert df["_source_url"].to_list() == [
        "https://dadosabertos.camara.leg.br/api/v2/proposicoes/100",
        "https://dadosabertos.camara.leg.br/api/v2/proposicoes/200",
    ]


# ── ProposicaoChildRouteExtractor (_source_url) ─────────────────────────────


@pytest.fixture
def tramitacoes_extractor() -> TramitacoesExtractor:
    ext = TramitacoesExtractor(client=AsyncMock())
    ext.base_url = "https://dadosabertos.camara.leg.br/api/v2"
    ext.fetch_unpaginated = AsyncMock()
    return ext


@pytest.mark.asyncio
async def test_tramitacoes_injects_source_url(tramitacoes_extractor: TramitacoesExtractor):
    """Cada registro deve ter _source_url apontando para /proposicoes/{id}/tramitacoes."""
    tramitacoes_extractor.fetch_unpaginated.return_value = [
        {"sequencia": 1, "descricao": "Recebida"},
    ]

    df = await tramitacoes_extractor.extract(proposicao_ids=[42])

    assert "_source_url" in df.columns
    assert df["_source_url"][0] == (
        "https://dadosabertos.camara.leg.br/api/v2/proposicoes/42/tramitacoes"
    )


@pytest.mark.asyncio
async def test_tramitacoes_source_url_mesmo_para_todos_registros(
    tramitacoes_extractor: TramitacoesExtractor,
):
    """Todos os registros de uma mesma proposição têm o mesmo _source_url."""
    tramitacoes_extractor.fetch_unpaginated.return_value = [
        {"sequencia": 1, "descricao": "Recebida"},
        {"sequencia": 2, "descricao": "Despachada"},
    ]

    df = await tramitacoes_extractor.extract(proposicao_ids=[42])

    expected = "https://dadosabertos.camara.leg.br/api/v2/proposicoes/42/tramitacoes"
    assert all(url == expected for url in df["_source_url"].to_list())


@pytest.mark.asyncio
async def test_tramitacoes_source_url_por_proposicao(
    tramitacoes_extractor: TramitacoesExtractor,
):
    """Registros de proposições diferentes têm _source_url diferentes."""
    tramitacoes_extractor.fetch_unpaginated.side_effect = [
        [{"sequencia": 1}],
        [{"sequencia": 1}],
    ]

    df = await tramitacoes_extractor.extract(proposicao_ids=[10, 20])

    assert df["_source_url"].to_list() == [
        "https://dadosabertos.camara.leg.br/api/v2/proposicoes/10/tramitacoes",
        "https://dadosabertos.camara.leg.br/api/v2/proposicoes/20/tramitacoes",
    ]


@pytest.mark.asyncio
async def test_tramitacoes_sem_ids_retorna_vazio(
    tramitacoes_extractor: TramitacoesExtractor,
):
    df = await tramitacoes_extractor.extract(proposicao_ids=None)
    assert df.is_empty()
    tramitacoes_extractor.fetch_unpaginated.assert_not_called()


@pytest.mark.asyncio
async def test_tramitacoes_adiciona_id_proposicao(
    tramitacoes_extractor: TramitacoesExtractor,
):
    tramitacoes_extractor.fetch_unpaginated.return_value = [
        {"sequencia": 1, "descricao": "Recebida"},
    ]

    df = await tramitacoes_extractor.extract(proposicao_ids=[42])

    assert "id_proposicao" in df.columns
    assert df["id_proposicao"][0] == 42
