"""Testes de _source_url para BlocoPartidosExtractor e FrenteMembrosExtractor."""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.camara.api.bloco_child import BlocoPartidosExtractor
from ipolitico.extractors.camara.api.frente_child import FrenteMembrosExtractor


class TestBlocoPartidosExtractorSourceUrl:
    """Testes de _source_url no BlocoPartidosExtractor."""

    @pytest.fixture
    def extractor(self) -> BlocoPartidosExtractor:
        ext = BlocoPartidosExtractor(client=AsyncMock())
        ext.base_url = "https://dadosabertos.camara.leg.br/api/v2"
        ext.fetch_unpaginated = AsyncMock()
        return ext

    @pytest.mark.asyncio
    async def test_extract_injects_source_url(self, extractor: BlocoPartidosExtractor):
        """Cada registro deve ter _source_url apontando para /blocos/{id}/partidos."""
        extractor.fetch_unpaginated.return_value = [
            {"id": 1, "sigla": "PT", "nome": "Partido dos Trabalhadores"},
        ]

        df = await extractor.extract(bloco_ids=[42])

        assert "_source_url" in df.columns
        assert (
            df["_source_url"][0] == "https://dadosabertos.camara.leg.br/api/v2/blocos/42/partidos"
        )

    @pytest.mark.asyncio
    async def test_extract_injects_source_url_multiplos_blocos(
        self, extractor: BlocoPartidosExtractor
    ):
        """Registros de blocos diferentes têm _source_url diferentes."""
        extractor.fetch_unpaginated.side_effect = [
            [{"id": 1, "sigla": "PT"}],
            [{"id": 2, "sigla": "PSDB"}],
        ]

        df = await extractor.extract(bloco_ids=[10, 20])

        assert df["_source_url"].to_list() == [
            "https://dadosabertos.camara.leg.br/api/v2/blocos/10/partidos",
            "https://dadosabertos.camara.leg.br/api/v2/blocos/20/partidos",
        ]

    @pytest.mark.asyncio
    async def test_extract_sem_ids_retorna_vazio(self, extractor: BlocoPartidosExtractor):
        df = await extractor.extract(bloco_ids=None)
        assert df.is_empty()
        extractor.fetch_unpaginated.assert_not_called()


class TestFrenteMembrosExtractorSourceUrl:
    """Testes de _source_url no FrenteMembrosExtractor."""

    @pytest.fixture
    def extractor(self) -> FrenteMembrosExtractor:
        ext = FrenteMembrosExtractor(client=AsyncMock())
        ext.base_url = "https://dadosabertos.camara.leg.br/api/v2"
        ext.fetch_unpaginated = AsyncMock()
        return ext

    @pytest.mark.asyncio
    async def test_extract_injects_source_url(self, extractor: FrenteMembrosExtractor):
        """Cada registro deve ter _source_url apontando para /frentes/{id}/membros."""
        extractor.fetch_unpaginated.return_value = [
            {"id": 100, "nome": "Deputado A"},
        ]

        df = await extractor.extract(frente_ids=[7])

        assert "_source_url" in df.columns
        assert df["_source_url"][0] == "https://dadosabertos.camara.leg.br/api/v2/frentes/7/membros"

    @pytest.mark.asyncio
    async def test_extract_sem_ids_retorna_vazio(self, extractor: FrenteMembrosExtractor):
        df = await extractor.extract(frente_ids=None)
        assert df.is_empty()
