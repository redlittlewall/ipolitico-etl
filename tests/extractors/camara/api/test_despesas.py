"""
Testes Unitários do Extrator de Despesas (API).
Focado na validação do fatiamento temporal (Job Matrix), filtros cirúrgicos
e injeção correta do DataFrame no Sink (Streaming In-Memory).
"""

from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest
from ipolitico.core.constants import ApiParams
from ipolitico.extractors.camara.api.despesas import DespesasExtractor


@pytest.fixture
def extractor():
    """Fornece um extrator com as dependências de rede e estado isoladas."""
    client = AsyncMock()
    state_store = MagicMock()
    ext = DespesasExtractor(client, state_store)
    # Mockamos a paginação para não batermos na API real da Câmara durante os testes
    ext.fetch_paginated = AsyncMock()
    return ext


@pytest.fixture
def mock_sink():
    """
    Mock da função sink_func (ex: SQLiteSink.save) para verificarmos o que o extrator tentou salvar.
    """
    return AsyncMock()


@pytest.mark.asyncio
async def test_extract_requires_explicit_params(extractor, mock_sink):
    """
    Garante que o extrator recusa trabalhar sem limites temporais ou IDs
    (Prevenindo Out of Memory ou chamadas infinitas).
    """
    with pytest.raises(ValueError, match="exige start_date, end_date e deputados_ids explícitos"):
        await extractor.extract(sink_func=mock_sink)

    with pytest.raises(ValueError):
        await extractor.extract(sink_func=mock_sink, deputados_ids=[1], start_date="2026-01-01")


@pytest.mark.asyncio
async def test_extract_job_matrix_generation(extractor, mock_sink):
    """
    Verifica se a lógica de fatiamento temporal gera os requests corretos para burlar a
    limitação da API.
    Uma busca de Nov/2025 a Fev/2026 deve gerar chamadas precisas para os meses 11, 12, 1 e 2.
    """
    extractor.fetch_paginated.return_value = []  # Retorna vazio para simplificar

    await extractor.extract(
        sink_func=mock_sink, deputados_ids=[100], start_date="2025-11-01", end_date="2026-02-28"
    )

    # 4 meses = 4 chamadas paginadas à API
    assert extractor.fetch_paginated.call_count == 4

    chamadas = [args[1] for args, kwargs in extractor.fetch_paginated.call_args_list]

    # Valida Ano e Mês das 4 chamadas geradas
    assert chamadas[0][ApiParams.ANO.value] == 2025 and chamadas[0][ApiParams.MES.value] == 11
    assert chamadas[1][ApiParams.ANO.value] == 2025 and chamadas[1][ApiParams.MES.value] == 12
    assert chamadas[2][ApiParams.ANO.value] == 2026 and chamadas[2][ApiParams.MES.value] == 1
    assert chamadas[3][ApiParams.ANO.value] == 2026 and chamadas[3][ApiParams.MES.value] == 2


@pytest.mark.asyncio
async def test_extract_streaming_to_sink(extractor, mock_sink):
    """
    Garante que os dados são capturados, filtrados e enviados diretamente para o Sink (Streaming),
    e que a chave 'id_deputado' foi injetada corretamente.
    """
    # Simulamos o retorno da API com duas despesas (uma dentro do prazo, outra fora)
    mock_api_response = [
        {"numDocumento": "A", "dataDocumento": "2026-01-15T10:00:00"},  # DENTRO
        {
            "numDocumento": "B",
            "dataDocumento": "2026-01-05T10:00:00",
        },  # FORA DO FILTRO (Será morta)
    ]
    extractor.fetch_paginated.return_value = mock_api_response

    # Janela temporal estrita: 10 de Jan a 20 de Jan
    await extractor.extract(
        sink_func=mock_sink, deputados_ids=[999], start_date="2026-01-10", end_date="2026-01-20"
    )

    # O Extrator DEVE ter chamado a nossa função de salvamento
    mock_sink.assert_called_once()

    # Vamos espiar o DataFrame que o extrator enviou para o Sink
    df_enviado_para_banco, table_name, unique_keys = mock_sink.call_args[0]

    assert isinstance(df_enviado_para_banco, pl.DataFrame)
    assert df_enviado_para_banco.height == 1  # Apenas a despesa "A" deve sobreviver ao filtro
    assert df_enviado_para_banco["numDocumento"][0] == "A"
    assert df_enviado_para_banco["id_deputado"][0] == 999  # Chave estrangeira injetada com sucesso

    # Valida parâmetros de contrato
    assert table_name == "despesas"
    assert unique_keys == ["id_deputado", "numDocumento", "codDocumento"]
