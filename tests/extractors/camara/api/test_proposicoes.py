"""Testes do ProposicoesExtractor (API)."""

from unittest.mock import AsyncMock

import pytest

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
