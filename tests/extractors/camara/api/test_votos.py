"""Testes do VotosExtractor — _source_url com votacao_id como resource_id."""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.camara.api.votos import VotosExtractor


@pytest.fixture
def extractor() -> VotosExtractor:
    client = AsyncMock()
    ext = VotosExtractor(client)
    return ext


@pytest.mark.asyncio
async def test_extract_sem_ids_retorna_vazio(extractor: VotosExtractor):
    """Sem votacao_ids, deve retornar DataFrame vazio."""
    df = await extractor.extract(votacao_ids=None)
    assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_injects_votacao_id(extractor: VotosExtractor):
    """Cada voto deve ter votacao_id e _source_url com /votacoes/{id}/votos."""
    extractor.client.fetch.return_value = [
        {"tipoVoto": "Sim", "deputado_": {"id": 1}},
        {"tipoVoto": "Não", "deputado_": {"id": 2}},
    ]

    df = await extractor.extract(votacao_ids=["V123"])

    assert df.height == 2
    assert df["votacao_id"].to_list() == ["V123", "V123"]
    assert df["_source_url"].to_list() == [
        "https://dadosabertos.camara.leg.br/api/v2/votacoes/V123/votos",
        "https://dadosabertos.camara.leg.br/api/v2/votacoes/V123/votos",
    ]


@pytest.mark.asyncio
async def test_extract_multiplas_votacoes(extractor: VotosExtractor):
    """Votos de múltiplas votações devem ter _source_url distinto por votacao_id."""
    extractor.client.fetch.side_effect = [
        [{"tipoVoto": "Sim", "deputado_": {"id": 1}}],
        [{"tipoVoto": "Não", "deputado_": {"id": 2}}],
    ]

    df = await extractor.extract(votacao_ids=["V1", "V2"])

    assert df.height == 2
    assert df["_source_url"].to_list() == [
        "https://dadosabertos.camara.leg.br/api/v2/votacoes/V1/votos",
        "https://dadosabertos.camara.leg.br/api/v2/votacoes/V2/votos",
    ]


@pytest.mark.asyncio
async def test_extract_vazio_retorna_vazio(extractor: VotosExtractor):
    """Se a API retornar lista vazia, deve retornar DataFrame vazio."""
    extractor.client.fetch.return_value = []

    df = await extractor.extract(votacao_ids=["V1"])

    assert df.is_empty()
