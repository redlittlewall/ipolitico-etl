from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest
from ipolitico.extractors.base import BaseExtractor, IStateStore


class DummyExtractor(BaseExtractor):
    """Extrator falso para testar apenas a classe abstrata."""

    async def extract(self):
        pass


@pytest.fixture
def mock_store():
    return MagicMock(spec=IStateStore)


@pytest.mark.asyncio
async def test_execute_concurrently_success(mock_store):
    """Garante que o motor assíncrono executa as tarefas e concatena os resultados corretamente."""
    extractor = DummyExtractor(mock_store)
    items = [1, 2, 3]

    async def dummy_fetch(item):
        return pl.DataFrame({"valor": [item]})

    df = await extractor.execute_concurrently(items, dummy_fetch)

    assert not df.is_empty()
    assert df.height == 3
    assert df["valor"].to_list() == [1, 2, 3]


@pytest.mark.asyncio
async def test_execute_concurrently_empty_items(mock_store):
    """Se não houver itens a processar, deve retornar DataFrame vazio silenciosamente."""
    extractor = DummyExtractor(mock_store)
    df = await extractor.execute_concurrently([], lambda x: pl.DataFrame())
    assert df.is_empty()


def test_base_extractor_get_watermark(mock_store):
    """Cobre o acesso ao state_store (linha 27)."""
    mock_store.get_watermark.return_value = "2026-01-01"
    extractor = DummyExtractor(mock_store)

    resultado = extractor._get_last_watermark("despesas", "dataDocumento")

    assert resultado == "2026-01-01"
    mock_store.get_watermark.assert_called_with("despesas", "dataDocumento")


@pytest.mark.asyncio
async def test_base_extractor_abstract_extract(mock_store):
    """Cobre a linha do 'pass' (linha 31) no @abstractmethod."""
    extractor = DummyExtractor(mock_store)
    # Aciona a implementação base vazia
    await BaseExtractor.extract(extractor)


@pytest.mark.asyncio
async def test_execute_pipeline_success(mock_store):
    """
    Testa o motor Producer-Consumer Anti-OOM (linha 81 e adjacentes).
    Garante que os DataFrames fluem da API para o Banco.
    """
    extractor = DummyExtractor(mock_store)
    items = [1, 2]

    async def mock_fetch(item):
        return pl.DataFrame({"id": [item]})

    mock_sink = AsyncMock()

    await extractor.execute_pipeline(
        items=items,
        fetch_func=mock_fetch,
        sink_func=mock_sink,
        table_name="minha_tabela",
        unique_keys="id",
    )

    # O sink deve ter sido chamado exatamente 2 vezes, uma para cada item processado
    assert mock_sink.call_count == 2


@pytest.mark.asyncio
async def test_execute_pipeline_empty_items(mock_store):
    """Garante que a pipeline aborta silenciosamente se não houver trabalho."""
    extractor = DummyExtractor(mock_store)
    mock_sink = AsyncMock()

    await extractor.execute_pipeline([], None, mock_sink, "minha_tabela")

    mock_sink.assert_not_called()
