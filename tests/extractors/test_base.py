from unittest.mock import MagicMock

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
