from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest
from ipolitico.core.constants import ApiParams
from ipolitico.extractors.camara.proposicoes import ProposicoesExtractor


@pytest.fixture
def extractor():
    client = AsyncMock()
    state_store = MagicMock()
    ext = ProposicoesExtractor(client, state_store)
    ext.fetch_paginated = AsyncMock()
    return ext


@pytest.mark.asyncio
async def test_extract_requires_dates(extractor):
    """Garante que o extrator trava se tentarem fazer uma busca não balizada."""
    with pytest.raises(ValueError, match="exige limites temporais explícitos"):
        await extractor.extract(start_date=None, end_date="2026-01-01")

    with pytest.raises(ValueError):
        await extractor.extract(start_date="2026-01-01", end_date=None)


@pytest.mark.asyncio
async def test_extract_year_matrix(extractor):
    """
    Se pedirmos dados de Dezembro de 2025 a Janeiro de 2026,
    o motor deve realizar buscas para o ano 2025 e para o ano 2026.
    """
    extractor.fetch_paginated.return_value = []

    await extractor.extract(start_date="2025-12-15", end_date="2026-01-15")

    assert extractor.fetch_paginated.call_count == 2

    chamadas = [args[1] for args, kwargs in extractor.fetch_paginated.call_args_list]

    assert chamadas[0][ApiParams.ANO] == 2025
    assert chamadas[1][ApiParams.ANO] == 2026


@pytest.mark.asyncio
async def test_extract_precision_filtering(extractor):
    """
    A API devolve o ano inteiro, mas o Polars deve cortar cirurgicamente
    apenas o que está dentro da janela do start_date e end_date.
    """
    mock_api_response = [
        {"id": 1, "dataApresentacao": "2026-03-01T14:30:00"},  # Fora (Antes)
        {"id": 2, "dataApresentacao": "2026-04-10T14:30:00"},  # DENTRO
        {"id": 3, "dataApresentacao": "2026-05-01T14:30:00"},  # Fora (Depois)
    ]
    extractor.fetch_paginated.return_value = mock_api_response

    # Janela restrita de 01 a 30 de Abril
    df_result = await extractor.extract(start_date="2026-04-01", end_date="2026-04-30")

    assert isinstance(df_result, pl.DataFrame)
    assert df_result.height == 1
    assert df_result["id"][0] == 2
