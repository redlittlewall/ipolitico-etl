import json
from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest
from ipolitico.extractors.camara.deputados import DeputadosExtractor


@pytest.fixture
def mock_deps_dependencies():
    client = AsyncMock()
    state_store = MagicMock()
    # Simulamos que o banco está vazio inicialmente
    state_store.get_existing_ids.return_value = []
    return client, state_store


@pytest.fixture
def extractor(mock_deps_dependencies):
    client, state_store = mock_deps_dependencies
    ext = DeputadosExtractor(client, state_store)
    # Mock do serviço de metadados interno
    ext.metadata.get_current_legislature_id = AsyncMock(return_value=57)
    # Mock da paginação da base
    ext.fetch_paginated = AsyncMock()
    return ext


@pytest.mark.asyncio
async def test_extract_with_dates(extractor):
    """Garante que filtros de data são passados corretamente para a API."""
    extractor.fetch_paginated.return_value = [{"id": 1, "nome": "Teste"}]

    await extractor.extract(start_date="2026-01-01", end_date="2026-01-31")

    args, kwargs = extractor.fetch_paginated.call_args
    params = args[1]
    assert params["dataInicio"] == "2026-01-01"
    assert params["dataFim"] == "2026-01-31"


@pytest.mark.asyncio
async def test_extract_full_load_logic(extractor):
    """Testa se o full_load percorre múltiplas legislaturas."""
    # Simulamos apenas 2 legislaturas para o teste ser rápido
    extractor.metadata.get_current_legislature_id.return_value = 2
    extractor.fetch_paginated.return_value = [{"id": 100, "nome": "Dep"}]

    # Mock do execute_concurrently para retornar dataframes de cada 'job'
    extractor.execute_concurrently = AsyncMock(
        return_value=pl.DataFrame([{"id": 100}, {"id": 200}])
    )

    df = await extractor.extract(full_load=True)

    assert isinstance(df, pl.DataFrame)
    extractor.execute_concurrently.assert_called_once()
    # Verifica se gerou a lista [1, 2] para processar
    args = extractor.execute_concurrently.call_args[0]
    assert args[0] == [1, 2]


@pytest.mark.asyncio
async def test_extract_detalhes_normalization(extractor):
    """
    CRITICAL: Garante que objetos complexos no JSON da API
    sejam convertidos para strings antes de ir para o banco.
    """
    complex_response = {
        "id": 1,
        "ultimoStatus": {"gabinete": "302", "situacao": "Exercício"},
        "redeSocial": ["twitter.com/deputado", "instagram.com/deputado"],
    }
    extractor.client.fetch = AsyncMock(return_value=complex_response)

    # Simulamos o execute_concurrently para retornar o resultado da função interna
    df = await extractor.extract_detalhes([1])

    # O Polars deve ter recebido strings JSON, não objetos Python
    # ultimoStatus deve ser string
    assert isinstance(df["ultimoStatus"][0], str)
    # redeSocial deve ser string
    assert isinstance(df["redeSocial"][0], str)

    # Verifica se os dados internos são recuperáveis
    data = json.loads(df["ultimoStatus"][0])
    assert data["gabinete"] == "302"


@pytest.mark.asyncio
async def test_get_all_ids_cache_logic(extractor):
    """Garante que não batemos na API se os IDs já existem no banco (StateStore)."""
    extractor.state_store.get_existing_ids.return_value = [1, 2, 3]

    ids = await extractor.get_all_ids()

    assert ids == [1, 2, 3]
    extractor.fetch_paginated.assert_not_called()
