from unittest.mock import AsyncMock, MagicMock

import pytest
from ipolitico.core.constants import ApiParams
from ipolitico.extractors.camara.deputados import DeputadosExtractor


# Fixtures (Preparação do ambiente de teste)
@pytest.fixture
def mock_client():
    client = AsyncMock()
    # Mock do fetch genérico para os detalhes
    client.fetch = AsyncMock()
    return client


@pytest.fixture
def mock_state_store():
    store = MagicMock()
    # Finge que já temos o deputado ID 1 no banco, mas não o 2
    store.get_existing_ids.return_value = [1]
    return store


@pytest.fixture
def extractor(mock_client, mock_state_store):
    # Injetamos as dependências falsas no extrator real
    ext = DeputadosExtractor(client=mock_client, state_store=mock_state_store)

    # Mockamos a paginação da classe base para não testar lógica HTTP aqui
    ext.fetch_paginated = AsyncMock()

    # Mock do serviço de metadados para não bater na API
    ext.metadata.get_current_legislature_id = AsyncMock(return_value=57)
    return ext


# --- BATERIA DE TESTES ---


@pytest.mark.asyncio
async def test_extract_com_filtros_explicitos(extractor):
    """Garante que se passarmos datas, ele foca no payload exato sem olhar para metadados."""
    # Dado que a API retorna um deputado
    extractor.fetch_paginated.return_value = [{"id": 1, "nome": "Fulano"}]

    # Quando chamamos com filtros
    df = await extractor.extract(start_date="2025-01-01", end_date="2025-12-31")

    # Então o DataFrame deve ser criado corretamente
    assert not df.is_empty()
    assert df.height == 1
    assert df["nome"][0] == "Fulano"

    # E o cliente HTTP deve ter sido chamado com as chaves de data corretas
    extractor.fetch_paginated.assert_called_once()
    args, kwargs = extractor.fetch_paginated.call_args
    params_enviados = args[1]

    assert ApiParams.DATA_INICIO.value in params_enviados
    assert params_enviados[ApiParams.DATA_INICIO.value] == "2025-01-01"


@pytest.mark.asyncio
async def test_extract_legislatura_atual_fallback(extractor):
    """Garante que sem filtros, ele busca apenas a legislatura atual por padrão."""
    extractor.fetch_paginated.return_value = [{"id": 2, "nome": "Ciclano"}]

    # Quando chamamos VAZIO e FULL_LOAD = False
    df = await extractor.extract(full_load=False)

    assert not df.is_empty()
    # Verifica se bateu no serviço de metadados para descobrir qual é a atual (57)
    extractor.metadata.get_current_legislature_id.assert_called_once()

    # Verifica se os parâmetros da chamada HTTP continham a legislatura 57
    args, kwargs = extractor.fetch_paginated.call_args
    params_enviados = args[1]
    assert params_enviados[ApiParams.ID_LEGISLATURA.value] == 57


@pytest.mark.asyncio
async def test_extract_detalhes_converte_dicionarios(extractor):
    """
    O extrator de detalhes DEVE converter dicionários/listas aninhados da API
    para JSON em string para não quebrar o banco SQLite.
    """
    # A API da Câmara retorna o 'ultimoStatus' como um sub-dicionário
    mock_resposta_api = {
        "id": 10,
        "nomeCivil": "Beltrano",
        "ultimoStatus": {"gabinete": "123", "situacao": "Exercício"},
    }
    extractor.client.fetch.return_value = mock_resposta_api

    df = await extractor.extract_detalhes(deputados_ids=[10])

    assert not df.is_empty()
    # Verifica se a chave foi transformada numa string JSON e não mantida como dict Python
    assert isinstance(df["ultimoStatus"][0], str)
    assert "gabinete" in df["ultimoStatus"][0]


@pytest.mark.asyncio
async def test_get_all_ids_usa_cache_do_banco(extractor, mock_state_store):
    """Se o banco já tem IDs, não devemos fazer requests HTTP desnecessários."""
    ids = await extractor.get_all_ids()

    assert ids == [1]
    # O fetch nunca deve ter sido chamado, poupando a rede
    extractor.fetch_paginated.assert_not_called()
