"""
Testes Unitários do Extrator de Votações (API).
Garante o particionamento temporal, a proteção contra Out of Memory
e a funcionalidade crítica de achatamento (flattening) dos dicionários de votos nominais.
"""

from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest
from ipolitico.extractors.camara.api.votacoes import VotacoesExtractor


@pytest.fixture
def extractor():
    """Fornece o extrator de Votações isolado da rede."""
    client = AsyncMock()
    state_store = MagicMock()
    ext = VotacoesExtractor(client, state_store)
    ext.fetch_paginated = AsyncMock()
    return ext


@pytest.fixture
def mock_sink():
    """Mock da função de gravação (Streaming Consumer)."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_extract_requires_dates(extractor, mock_sink):
    """Garante que a extração de votações exige limites temporais explícitos."""
    with pytest.raises(ValueError, match="exige limites temporais explícitos"):
        await extractor.extract(sink_func=mock_sink, start_date=None, end_date="2026-01-01")


@pytest.mark.asyncio
async def test_extract_year_splitting(extractor, mock_sink):
    """
    Testa se o particionamento temporal funciona.
    Uma janela que cruza o ano deve gerar requisições delimitadas para não estourar a API.
    """
    extractor.execute_pipeline = AsyncMock()

    await extractor.extract(sink_func=mock_sink, start_date="2025-11-01", end_date="2026-02-01")

    extractor.execute_pipeline.assert_called_once()

    kwargs = extractor.execute_pipeline.call_args[1]
    # Valida se os anos foram fatiados corretamente
    assert kwargs["items"] == [2025, 2026]
    assert kwargs["table_name"] == "votacoes"


@pytest.mark.asyncio
async def test_extract_votos_streaming_and_flattening(extractor, mock_sink):
    """
    CRÍTICO: A API da Câmara retorna o deputado dentro de um dicionário ('deputado_').
    O extrator deve extrair os dados relacionais, destruir o dicionário e enviar
    tudo de imediato para o Sink (Streaming In-Memory).
    """
    mock_voto_api = [
        {
            "tipoVoto": "Sim",
            "dataRegistroVoto": "2026-01-01T10:00:00",
            "deputado_": {
                "id": 999,
                "nome": "Deputado Falso",
                "siglaPartido": "XPTO",
                "siglaUf": "SP",
            },
        }
    ]

    extractor.client.fetch.return_value = mock_voto_api

    # Dispara a extração de votos num lote pequeno
    await extractor.extract_votos(sink_func=mock_sink, votacoes_ids=["ID_VOTACAO_1"])

    mock_sink.assert_called_once()
    df_salvo, table_name, unique_keys = mock_sink.call_args[0]

    assert isinstance(df_salvo, pl.DataFrame)
    assert df_salvo.height == 1

    # Verifica se a chave estrangeira da votação foi injetada no worker
    assert df_salvo["idVotacao"][0] == "ID_VOTACAO_1"

    # Verifica se os dados do dicionário subiram para o nível raiz
    assert df_salvo["deputado_id"][0] == 999
    assert df_salvo["partido_no_voto"][0] == "XPTO"

    # Garante que o dicionário venenoso foi aniquilado antes de tocar no banco
    assert "deputado_" not in df_salvo.columns

    assert table_name == "votos"
    assert unique_keys == ["idVotacao", "deputado_id"]


@pytest.mark.asyncio
async def test_extract_votos_simbolicos(extractor, mock_sink):
    """
    Votações simbólicas retornam um array vazio (devido ao nosso tratamento de 404 no client).
    O extrator deve lidar com isso ignorando o salvamento em vez de falhar.
    """
    extractor.client.fetch.return_value = []

    await extractor.extract_votos(sink_func=mock_sink, votacoes_ids=["VOTACAO_SIMBOLICA_1"])

    # Como o DataFrame gerado é vazio, a pipeline NÃO deve chamar o sink
    mock_sink.assert_not_called()
