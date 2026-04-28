"""
Testes Unitários do Extrator de Deputados (API).
Valida a geração de matriz de legislaturas (Full Load vs Atual)
e a normalização estrita de JSONs complexos nos detalhes cadastrais.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from ipolitico.extractors.camara.api.deputados import DeputadosExtractor


@pytest.fixture
def mock_deps_dependencies():
    """Fornece mocks isolados de rede e banco de dados."""
    client = AsyncMock()
    state_store = MagicMock()
    # Simulamos que o banco está vazio inicialmente
    state_store.get_existing_ids.return_value = []
    return client, state_store


@pytest.fixture
def extractor(mock_deps_dependencies):
    """Instancia o extrator de Deputados com injeção de dependências mockadas."""
    client, state_store = mock_deps_dependencies
    ext = DeputadosExtractor(client, state_store)

    # Mock do serviço de metadados interno (fingimos estar na Legislatura 2)
    ext.metadata.get_current_legislature_id = AsyncMock(return_value=2)

    # Mock da paginação
    ext.fetch_paginated = AsyncMock()
    return ext


@pytest.fixture
def mock_sink():
    """Mock da função sink_func (ex: SQLiteSink.save) para interceptar os DataFrames."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_extract_with_dates(extractor, mock_sink):
    """
    Garante que os filtros de data são passados corretamente para a API
    e enviados diretamente para o Sink sem passar pelo pipeline de legislaturas.
    """
    extractor.fetch_paginated.return_value = [{"id": 1, "nome": "João Político"}]

    await extractor.extract(sink_func=mock_sink, start_date="2026-01-01", end_date="2026-01-31")

    # Verifica se a API foi chamada com os parâmetros corretos
    args, kwargs = extractor.fetch_paginated.call_args
    params = args[1]
    assert params["dataInicio"] == "2026-01-01"
    assert params["dataFim"] == "2026-01-31"

    # Verifica se o Sink recebeu o DataFrame com o contrato correto
    mock_sink.assert_called_once()
    df_salvo, table_name, unique_keys = mock_sink.call_args[0]
    assert df_salvo.height == 1
    assert table_name == "deputados"
    assert unique_keys == "id"


@pytest.mark.asyncio
async def test_extract_full_load_matrix(extractor, mock_sink):
    """
    Testa se o full_load gera os jobs corretamente varrendo todas as legislaturas
    desde o Império até a legislatura mockada atual (1 até 2).
    """
    # Mockamos a função base execute_pipeline para não disparar a concorrência real
    extractor.execute_pipeline = AsyncMock()

    await extractor.extract(sink_func=mock_sink, full_load=True)

    extractor.execute_pipeline.assert_called_once()

    # Valida se a matriz de tarefas (items) mandou processar as legislaturas [1, 2]
    kwargs = extractor.execute_pipeline.call_args[1]
    assert kwargs["items"] == [1, 2]
    assert kwargs["table_name"] == "deputados"


@pytest.mark.asyncio
async def test_extract_detalhes_normalization(extractor, mock_sink):
    """
    CRÍTICO (Blindagem de Schema): Garante que objetos complexos (dict/list) no
    JSON da API sejam serializados para string antes de entrarem no Sink,
    evitando falhas de tipagem no SQLite ou Parquet.
    """
    complex_response = {
        "id": 999,
        "nome": "Maria Política",
        "ultimoStatus": {"gabinete": "302", "situacao": "Exercício"},  # Isto é um Dict
        "redeSocial": ["twitter.com/deputada", "instagram.com/deputada"],  # Isto é uma List
    }
    extractor.client.fetch = AsyncMock(return_value=complex_response)

    # Dispara a extração de detalhes
    await extractor.extract_detalhes(sink_func=mock_sink, deputados_ids=[999])

    # Interceta o DataFrame que o extrator tentou gravar
    mock_sink.assert_called_once()
    df_salvo = mock_sink.call_args[0][0]

    # O Polars deve ter recebido strings JSON, não objetos Python puros
    assert isinstance(df_salvo["ultimoStatus"][0], str)
    assert isinstance(df_salvo["redeSocial"][0], str)

    # Verifica se os dados internos são recuperáveis a partir da string
    data_status = json.loads(df_salvo["ultimoStatus"][0])
    assert data_status["gabinete"] == "302"
    assert data_status["situacao"] == "Exercício"
