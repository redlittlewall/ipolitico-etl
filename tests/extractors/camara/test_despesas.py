from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest
from ipolitico.core.constants import ApiParams
from ipolitico.extractors.camara.despesas import DespesasExtractor


@pytest.fixture
def extractor():
    client = AsyncMock()
    state_store = MagicMock()
    ext = DespesasExtractor(client, state_store)
    ext.fetch_paginated = AsyncMock()
    return ext


@pytest.mark.asyncio
async def test_extract_requires_explicit_params(extractor):
    """
    Garante que o extrator recusa trabalhar sem limites temporais ou IDs
    (Evita Out of Memory).
    """
    with pytest.raises(ValueError, match="exige start_date, end_date e deputados_ids explícitos"):
        await extractor.extract()

    with pytest.raises(ValueError):
        await extractor.extract(deputados_ids=[1], start_date="2026-01-01")


@pytest.mark.asyncio
async def test_extract_job_matrix_generation(extractor):
    """
    Verifica se a lógica de fatiamento temporal gera os requests corretos.
    Uma busca de Nov/2025 a Fev/2026 deve gerar chamadas para os meses 11, 12, 1 e 2.
    """
    extractor.fetch_paginated.return_value = []  # Retorna vazio para simplificar

    await extractor.extract(deputados_ids=[100], start_date="2025-11-01", end_date="2026-02-28")

    assert extractor.fetch_paginated.call_count == 4

    chamadas = [args[1] for args, kwargs in extractor.fetch_paginated.call_args_list]

    # Valida Ano e Mês das 4 chamadas geradas
    assert chamadas[0][ApiParams.ANO] == 2025 and chamadas[0][ApiParams.MES] == 11
    assert chamadas[1][ApiParams.ANO] == 2025 and chamadas[1][ApiParams.MES] == 12
    assert chamadas[2][ApiParams.ANO] == 2026 and chamadas[2][ApiParams.MES] == 1
    assert chamadas[3][ApiParams.ANO] == 2026 and chamadas[3][ApiParams.MES] == 2


@pytest.mark.asyncio
async def test_extract_success_with_strict_filtering(extractor):
    """
    Garante que os dados são capturados, a chave 'id_deputado' é injetada
    e o filtro de precisão remove despesas fora da janela exata.
    """
    # Simulamos o retorno da API com duas despesas (uma dentro do prazo, outra fora)
    mock_api_response = [
        {"numDocumento": "A", "dataDocumento": "2026-01-15T10:00:00"},
        {"numDocumento": "B", "dataDocumento": "2026-01-05T10:00:00"},
    ]
    extractor.fetch_paginated.return_value = mock_api_response

    # Janela temporal: 10 de Jan a 20 de Jan
    df_result = await extractor.extract(
        deputados_ids=[999], start_date="2026-01-10", end_date="2026-01-20"
    )

    assert isinstance(df_result, pl.DataFrame)
    assert not df_result.is_empty()
    assert df_result.height == 1  # Apenas a despesa "A" deve sobreviver
    assert df_result["numDocumento"][0] == "A"
    assert df_result["id_deputado"][0] == 999  # Chave estrangeira injetada com sucesso
