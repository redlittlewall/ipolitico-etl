"""Testes de _source_url para ReferenciasExtractor."""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.camara.api.referencias import ReferenciasExtractor


class TestReferenciasExtractorSourceUrl:
    """Testes de _source_url no ReferenciasExtractor."""

    @pytest.fixture
    def extractor(self) -> ReferenciasExtractor:
        ext = ReferenciasExtractor(client=AsyncMock())
        ext.base_url = "https://dadosabertos.camara.leg.br/api/v2"
        ext.fetch_unpaginated = AsyncMock()
        return ext

    @pytest.mark.asyncio
    async def test_extract_injects_source_url(self, extractor: ReferenciasExtractor):
        """Cada registro deve ter _source_url apontando para /referencias/{tipo}."""
        extractor.fetch_unpaginated.return_value = [
            {"cod": 1, "nome": "Acre", "sigla": "AC"},
        ]

        df = await extractor.extract(routes=["referencias/uf"])

        assert "_source_url" in df.columns
        assert df["_source_url"][0] == "https://dadosabertos.camara.leg.br/api/v2/referencias/uf"

    @pytest.mark.asyncio
    async def test_source_url_por_referencia(self, extractor: ReferenciasExtractor):
        """Registros de referências diferentes têm _source_url diferentes."""
        extractor.fetch_unpaginated.side_effect = [
            [{"cod": 1, "nome": "Acre"}],
            [{"cod": 10, "nome": "Partido A"}],
        ]

        df = await extractor.extract(routes=["referencias/uf", "referencias/deputados"])

        assert df["_source_url"].to_list() == [
            "https://dadosabertos.camara.leg.br/api/v2/referencias/uf",
            "https://dadosabertos.camara.leg.br/api/v2/referencias/deputados",
        ]

    @pytest.mark.asyncio
    async def test_extract_adiciona_coluna_referencia(self, extractor: ReferenciasExtractor):
        """Cada registro deve ter a coluna 'referencia' com o path."""
        extractor.fetch_unpaginated.return_value = [
            {"cod": 1, "nome": "Acre"},
        ]

        df = await extractor.extract(routes=["referencias/uf"])

        assert "referencia" in df.columns
        assert df["referencia"][0] == "referencias/uf"

    @pytest.mark.asyncio
    async def test_extract_sem_rotas_usa_padrao(self, extractor: ReferenciasExtractor):
        """Se routes=None, usa REFERENCE_ROUTES."""
        extractor.fetch_unpaginated.return_value = [
            {"cod": 1, "sigla": "AC", "nome": "Acre"},
        ]

        await extractor.extract(routes=None)

        # Deve ter chamado fetch_unpaginated para ao menos 1 rota
        assert extractor.fetch_unpaginated.call_count > 1

    @pytest.mark.asyncio
    async def test_extract_vazio(self, extractor: ReferenciasExtractor):
        """Se API retornar lista vazia, retorna DataFrame vazio."""
        extractor.fetch_unpaginated.return_value = []

        df = await extractor.extract(routes=["referencias/uf"])

        assert df.is_empty()
