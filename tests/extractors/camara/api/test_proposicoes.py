"""
Testes Unitários do Extrator de Proposições (API).
Valida o fracionamento por anos, proteção de parâmetros obrigatórios
e o filtro cirúrgico que impede vazamento de dados fora da janela requisitada.
"""

from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest
from ipolitico.extractors.camara.api.proposicoes import ProposicoesExtractor


@pytest.fixture
def extractor():
    """Fornece o extrator de Proposições com dependências isoladas."""
    client = AsyncMock()
    state_store = MagicMock()
    ext = ProposicoesExtractor(client, state_store)

    # Interceptamos a paginação para não sobrecarregar a API do governo
    ext.fetch_paginated = AsyncMock()
    return ext


@pytest.fixture
def mock_sink():
    """Mock da função de salvamento (sink_func) para auditar os DataFrames gerados."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_extract_requires_dates(extractor, mock_sink):
    """
    Garante que o extrator trava imediatamente (Fail-Fast) se tentarem
    fazer uma busca não balizada, o que causaria um Out of Memory ou bloqueio da API.
    """
    with pytest.raises(ValueError, match="exige limites temporais explícitos"):
        await extractor.extract(sink_func=mock_sink, start_date=None, end_date="2026-01-01")

    with pytest.raises(ValueError):
        await extractor.extract(sink_func=mock_sink, start_date="2026-01-01", end_date=None)


@pytest.mark.asyncio
async def test_extract_year_matrix(extractor, mock_sink):
    """
    Testa se o motor de agendamento gera os jobs corretos.
    Se pedirmos de Dezembro de 2025 a Janeiro de 2026, ele deve acionar a
    pipeline assíncrona mandando extrair os anos [2025, 2026].
    """
    # Mockamos a pipeline base para interceptar os parâmetros enviados
    extractor.execute_pipeline = AsyncMock()

    await extractor.extract(sink_func=mock_sink, start_date="2025-12-15", end_date="2026-01-15")

    extractor.execute_pipeline.assert_called_once()

    kwargs = extractor.execute_pipeline.call_args[1]
    # Valida se os itens (anos) foram calculados corretamente para os workers
    assert kwargs["items"] == [2025, 2026]
    assert kwargs["table_name"] == "proposicoes"
    assert kwargs["unique_keys"] == "id"


@pytest.mark.asyncio
async def test_extract_precision_filtering(extractor, mock_sink):
    """
    A API devolve o ano inteiro, mas o Polars deve cortar cirurgicamente
    apenas o que está dentro da janela do start_date e end_date antes de enviar ao Sink.
    """
    mock_api_response = [
        {"id": 1, "dataApresentacao": "2026-03-01T14:30:00"},  # Fora (Antes)
        {"id": 2, "dataApresentacao": "2026-04-10T14:30:00"},  # DENTRO DA JANELA
        {"id": 3, "dataApresentacao": "2026-05-01T14:30:00"},  # Fora (Depois)
    ]
    extractor.fetch_paginated.return_value = mock_api_response

    # Dispara a extração numa janela restrita de Abril
    await extractor.extract(sink_func=mock_sink, start_date="2026-04-01", end_date="2026-04-30")

    # O Extrator DEVE ter chamado a função de salvamento apenas uma vez
    mock_sink.assert_called_once()

    df_salvo = mock_sink.call_args[0][0]

    assert isinstance(df_salvo, pl.DataFrame)
    assert df_salvo.height == 1  # O registro 1 e 3 devem ter sido expurgados da memória
    assert df_salvo["id"][0] == 2
