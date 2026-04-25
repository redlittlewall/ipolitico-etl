from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest
from ipolitico.extractors.camara.votacoes import VotacoesExtractor


@pytest.fixture
def extractor():
    client = AsyncMock()
    state_store = MagicMock()
    ext = VotacoesExtractor(client, state_store)
    ext.fetch_paginated = AsyncMock()
    return ext


@pytest.mark.asyncio
async def test_extract_requires_dates(extractor):
    """Garante que a extração de votações exige limites temporais explícitos."""
    with pytest.raises(ValueError, match="exige limites temporais explícitos"):
        await extractor.extract(start_date=None, end_date="2026-01-01")


@pytest.mark.asyncio
async def test_extract_year_splitting(extractor):
    """
    Testa se o particionamento temporal funciona.
    Uma janela que cruza o ano deve gerar requisições delimitadas para não estourar a API.
    """
    extractor.fetch_paginated.return_value = []

    await extractor.extract(start_date="2025-11-01", end_date="2026-02-01")

    assert extractor.fetch_paginated.call_count == 2

    chamadas = [args[1] for args, kwargs in extractor.fetch_paginated.call_args_list]

    # Valida a requisição de 2025 (Deve ir do start_date até o fim do ano)
    assert chamadas[0]["dataInicio"] == "2025-11-01"
    assert chamadas[0]["dataFim"] == "2025-12-31"

    # Valida a requisição de 2026 (Deve ir do começo do ano até o end_date)
    assert chamadas[1]["dataInicio"] == "2026-01-01"
    assert chamadas[1]["dataFim"] == "2026-02-01"


@pytest.mark.asyncio
async def test_extract_votos_flattening(extractor):
    """
    CRÍTICO: A API da Câmara retorna o deputado dentro de um dicionário ('deputado_').
    O extrator deve extrair os dados relacionais e DESTRUIR o dicionário para
    que o banco SQLite (tipagem forte) não rejeite o insert.
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

    df_result = await extractor.extract_votos(["ID_VOTACAO_1"])

    assert isinstance(df_result, pl.DataFrame)
    assert df_result.height == 1

    # Verifica se a chave estrangeira da votação foi injetada
    assert df_result["idVotacao"][0] == "ID_VOTACAO_1"

    # Verifica se os dados do dicionário subiram para o nível raiz
    assert df_result["deputado_id"][0] == 999
    assert df_result["partido_no_voto"][0] == "XPTO"

    # Garante que o dicionário venenoso foi aniquilado
    assert "deputado_" not in df_result.columns


@pytest.mark.asyncio
async def test_extract_votos_simbolicos(extractor):
    """
    Votações simbólicas retornam um array vazio (devido ao nosso tratamento de 404 no client).
    O extrator deve lidar com isso retornando um DataFrame vazio em vez de quebrar.
    """
    extractor.client.fetch.return_value = []

    df_result = await extractor.extract_votos(["VOTACAO_SIMBOLICA_1"])

    assert isinstance(df_result, pl.DataFrame)
    assert df_result.is_empty()
