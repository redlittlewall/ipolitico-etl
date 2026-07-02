"""Testes do OrientacoesExtractor — _source_url com votacao_id como resource_id."""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.camara.api.votacao_child import (
    OrientacoesExtractor,
    VotacaoChildRouteExtractor,
)


class TestOrientacoesExtractor:
    def test_route_suffix(self):
        """route_suffix deve ser 'orientacoes'."""
        assert OrientacoesExtractor.route_suffix == "orientacoes"

    def test_eh_subclasse_de_votacao_child(self):
        """OrientacoesExtractor deve herdar de VotacaoChildRouteExtractor."""
        assert issubclass(OrientacoesExtractor, VotacaoChildRouteExtractor)

    def test_source_url_format_definido(self):
        """source_url_format deve estar definido."""
        ext = OrientacoesExtractor(client=AsyncMock())
        assert ext.source_url_format is not None
        assert "{resource_id}" in ext.source_url_format


@pytest.fixture
def extractor() -> OrientacoesExtractor:
    ext = OrientacoesExtractor(client=AsyncMock())
    return ext


@pytest.mark.asyncio
async def test_extract_sem_ids_retorna_vazio(extractor: OrientacoesExtractor):
    """Sem votacao_ids, deve retornar DataFrame vazio."""
    df = await extractor.extract(votacao_ids=None)
    assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_injects_votacao_id_e_source_url(extractor: OrientacoesExtractor):
    """Cada orientação deve ter votacao_id e _source_url."""
    extractor.client.fetch.return_value = [
        {"orientacaoVoto": "Sim", "siglaPartidoBloco": "PT"},
        {"orientacaoVoto": "Não", "siglaPartidoBloco": "PSDB"},
    ]

    df = await extractor.extract(votacao_ids=["V99"])

    assert df.height == 2
    assert df["votacao_id"].to_list() == ["V99", "V99"]
    assert df["_source_url"].to_list() == [
        "https://dadosabertos.camara.leg.br/api/v2/votacoes/V99/orientacoes",
        "https://dadosabertos.camara.leg.br/api/v2/votacoes/V99/orientacoes",
    ]


@pytest.mark.asyncio
async def test_extract_multiplas_votacoes(extractor: OrientacoesExtractor):
    """Múltiplas votações geram _source_url distinto."""
    extractor.client.fetch.side_effect = [
        [{"orientacaoVoto": "Sim", "siglaPartidoBloco": "PT"}],
        [{"orientacaoVoto": "Libera", "siglaPartidoBloco": "MDB"}],
    ]

    df = await extractor.extract(votacao_ids=["V1", "V2"])

    assert df.height == 2
    assert df["_source_url"].to_list() == [
        "https://dadosabertos.camara.leg.br/api/v2/votacoes/V1/orientacoes",
        "https://dadosabertos.camara.leg.br/api/v2/votacoes/V2/orientacoes",
    ]
