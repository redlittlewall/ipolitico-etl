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


@pytest.mark.asyncio
async def test_fetch_votacoes_ano_logic(extractor):
    """
    [Cobre Linhas 45-63]
    Como a função fetch_votacoes_ano está enclausurada dentro de extract(),
    precisamos capturá-la no mock do pipeline para garantir que as regras
    de negócio (corte de datas e filtro Polars) funcionam perfeitamente.
    """
    mock_sink = AsyncMock()
    extractor.execute_pipeline = AsyncMock()

    # Rodamos o extrator na janela de cruzamento de ano
    await extractor.extract(sink_func=mock_sink, start_date="2025-11-01", end_date="2026-02-01")

    # Interceptamos a função injetada no motor Producer-Consumer
    kwargs = extractor.execute_pipeline.call_args.kwargs
    fetch_func = kwargs["fetch_func"]

    # Simulamos o retorno bruto (sujo) da API da Câmara para o ano de 2025
    extractor.fetch_paginated.return_value = [
        {"id": "VOT-1", "data": "2025-10-31T10:00:00"},  # Fora da janela (antes)
        {"id": "VOT-2", "data": "2025-12-15T10:00:00"},  # Dentro da janela
    ]

    # Executamos o worker interno isoladamente
    df_2025 = await fetch_func(2025)

    # Validação da Blindagem de Dados: o Polars deve ter cortado o VOT-1
    assert not df_2025.is_empty()
    assert df_2025.height == 1
    assert df_2025["id"][0] == "VOT-2"

    # Garante que as datas enviadas na URL respeitam os limites daquele ano específico
    api_params = extractor.fetch_paginated.call_args[0][1]
    assert api_params["dataInicio"] == "2025-11-01"
    assert api_params["dataFim"] == "2025-12-31"


@pytest.mark.asyncio
async def test_extract_votos_empty_ids(extractor):
    """
    [Cobre Linha 85]
    Valida a quebra antecipada (early return) se a lista de votações enviada for vazia.
    Testa o lixo de refatoração do return pl.DataFrame().
    """
    mock_sink = AsyncMock()
    extractor.execute_pipeline = AsyncMock()

    # Se passarmos uma lista vazia, ele deve abortar antes de acionar a concorrência
    resultado = await extractor.extract_votos(sink_func=mock_sink, votacoes_ids=[])

    assert isinstance(resultado, pl.DataFrame)
    assert resultado.is_empty()

    # O pipeline não pode ter sido chamado
    extractor.execute_pipeline.assert_not_called()
