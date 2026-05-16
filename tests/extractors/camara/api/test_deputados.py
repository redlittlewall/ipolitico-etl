"""Testes do DeputadosExtractor (API) — extrator retorna DataFrame bruto."""

from unittest.mock import AsyncMock

import pytest
from ipolitico.extractors.camara.api.deputados import DeputadosExtractor


@pytest.fixture
def extractor() -> DeputadosExtractor:
    client = AsyncMock()
    ext = DeputadosExtractor(client)
    ext.fetch_paginated = AsyncMock()
    return ext


@pytest.mark.asyncio
async def test_extract_passes_date_filters_to_api(extractor: DeputadosExtractor):
    extractor.fetch_paginated.return_value = [{"id": 1, "nome": "João Político"}]

    df = await extractor.extract(start_date="2026-01-01", end_date="2026-01-31")

    assert df.height == 1
    _endpoint, params = extractor.fetch_paginated.call_args[0]
    assert params["dataInicio"] == "2026-01-01"
    assert params["dataFim"] == "2026-01-31"


@pytest.mark.asyncio
async def test_extract_empty_api_returns_empty_frame(extractor: DeputadosExtractor):
    extractor.fetch_paginated.return_value = []

    df = await extractor.extract(start_date="2026-01-01", end_date="2026-01-31")

    assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_detalhes_builds_row_dataframe(extractor: DeputadosExtractor):
    complex_response = {
        "id": 999,
        "nome": "Maria Política",
        "ultimoStatus": {"gabinete": "302", "situacao": "Exercício"},
    }
    extractor.client.fetch = AsyncMock(return_value=complex_response)

    df = await extractor.extract_detalhes(999)

    assert df.height == 1
    assert df["id"][0] == 999


@pytest.mark.asyncio
async def test_extract_detalhes_empty_response(extractor: DeputadosExtractor):
    extractor.client.fetch = AsyncMock(return_value={})

    df = await extractor.extract_detalhes(99)

    assert df.is_empty()
