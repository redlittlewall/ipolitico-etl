"""Testes do VotacoesExtractor (API)."""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.camara.api.votacoes import VotacoesExtractor


@pytest.fixture
def extractor() -> VotacoesExtractor:
    client = AsyncMock()
    ext = VotacoesExtractor(client)
    ext.fetch_paginated = AsyncMock()
    return ext


@pytest.mark.asyncio
async def test_extract_passes_date_range(extractor: VotacoesExtractor):
    extractor.fetch_paginated.return_value = [{"id": "V1", "data": "2026-01-15"}]

    df = await extractor.extract(start_date="2026-01-01", end_date="2026-01-31")

    assert df.height == 1
    _route, params = extractor.fetch_paginated.call_args[0]
    assert params["dataInicio"] == "2026-01-01"
    assert params["dataFim"] == "2026-01-31"


@pytest.mark.asyncio
async def test_extract_empty_returns_empty(extractor: VotacoesExtractor):
    extractor.fetch_paginated.return_value = []

    df = await extractor.extract(start_date="2026-01-01", end_date="2026-01-31")

    assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_votos_returns_list_as_dataframe(extractor: VotacoesExtractor):
    extractor.client.fetch.return_value = [
        {
            "tipoVoto": "Sim",
            "deputado_": {"id": 999, "siglaPartido": "X", "siglaUf": "SP"},
        }
    ]

    df = await extractor.extract_votos("VOT-1")

    assert df.height == 1
    assert "tipoVoto" in df.columns


@pytest.mark.asyncio
async def test_extract_votos_empty_list_returns_empty(extractor: VotacoesExtractor):
    extractor.client.fetch.return_value = []

    df = await extractor.extract_votos("SIMB")

    assert df.is_empty()
