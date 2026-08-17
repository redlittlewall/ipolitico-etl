"""Testes do extrator de despesas (API): fetch paginado e injeção de id_deputado."""

from unittest.mock import AsyncMock

import pytest

from ipolitico.core.constants import ApiParams
from ipolitico.extractors.camara.api.despesas import DespesasExtractor


@pytest.fixture
def extractor():
    client = AsyncMock()
    client.BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
    ext = DespesasExtractor(client)
    ext.fetch_paginated = AsyncMock()
    return ext


@pytest.mark.asyncio
async def test_extract_returns_empty_when_api_empty(extractor):
    extractor.fetch_paginated.return_value = []

    df = await extractor.extract(deputado_id=100, year=2026, month=11)

    assert df.is_empty()
    extractor.fetch_paginated.assert_called_once()


@pytest.mark.asyncio
async def test_extract_injects_deputado_id_and_builds_params(extractor):
    extractor.fetch_paginated.return_value = [
        {"numDocumento": "A", "dataDocumento": "2026-01-15T10:00:00"},
    ]

    df = await extractor.extract(deputado_id=999, year=2026, month=1)

    assert not df.is_empty()
    assert df["id_deputado"][0] == 999
    call_params = extractor.fetch_paginated.call_args[0][1]
    assert call_params[ApiParams.ANO.value] == 2026
    assert call_params[ApiParams.MES.value] == 1


@pytest.mark.asyncio
async def test_extract_injects_source_url(extractor):
    """Despesas com mês devem ter _source_url com ano e mes."""
    extractor.fetch_paginated.return_value = [
        {"numDocumento": "A", "dataDocumento": "2026-01-15T10:00:00"},
    ]

    df = await extractor.extract(deputado_id=999, year=2026, month=1)

    assert "_source_url" in df.columns
    assert (
        df["_source_url"][0]
        == "https://dadosabertos.camara.leg.br/api/v2/deputados/999/despesas?ano=2026&mes=1"
    )


@pytest.mark.asyncio
async def test_extract_injects_source_url_sem_mes(extractor):
    """Despesas sem mês devem ter _source_url apenas com ano."""
    extractor.fetch_paginated.return_value = [
        {"numDocumento": "A", "dataDocumento": "2026-01-15T10:00:00"},
    ]

    df = await extractor.extract(deputado_id=888, year=2026)

    assert "_source_url" in df.columns
    assert (
        df["_source_url"][0]
        == "https://dadosabertos.camara.leg.br/api/v2/deputados/888/despesas?ano=2026"
    )
