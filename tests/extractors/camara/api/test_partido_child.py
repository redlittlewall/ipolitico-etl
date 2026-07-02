"""Testes de _source_url para PartidoChildRouteExtractor e subclasses."""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.camara.api.partido_child import (
    PartidoLideresExtractor,
    PartidoMembrosExtractor,
)


class BasePartidoChildTest:
    """Testes genéricos para subclasses de PartidoChildRouteExtractor."""

    extractor_cls = None
    route_suffix = ""

    @pytest.fixture
    def extractor(self):
        ext = self.extractor_cls(client=AsyncMock())
        ext.base_url = "https://dadosabertos.camara.leg.br/api/v2"
        ext.fetch_paginated = AsyncMock()
        return ext

    @pytest.mark.asyncio
    async def test_extract_injects_source_url(self, extractor):
        extractor.fetch_paginated.return_value = [
            {"id": 1, "nome": "Membro A"},
        ]

        df = await extractor.extract(partido_ids=[13])

        assert "_source_url" in df.columns
        expected = f"https://dadosabertos.camara.leg.br/api/v2/partidos/13/{self.route_suffix}"
        assert df["_source_url"][0] == expected

    @pytest.mark.asyncio
    async def test_extract_sem_ids_retorna_vazio(self, extractor):
        df = await extractor.extract(partido_ids=None)
        assert df.is_empty()
        extractor.fetch_paginated.assert_not_called()

    @pytest.mark.asyncio
    async def test_adiciona_id_partido(self, extractor):
        extractor.fetch_paginated.return_value = [
            {"id": 1, "nome": "Membro A"},
        ]

        df = await extractor.extract(partido_ids=[13])

        assert "id_partido" in df.columns
        assert df["id_partido"][0] == 13

    @pytest.mark.asyncio
    async def test_source_url_mesmo_para_todos_registros_mesmo_partido(self, extractor):
        extractor.fetch_paginated.return_value = [
            {"id": 1, "nome": "Membro A"},
            {"id": 2, "nome": "Membro B"},
        ]

        df = await extractor.extract(partido_ids=[13])

        expected = f"https://dadosabertos.camara.leg.br/api/v2/partidos/13/{self.route_suffix}"
        assert all(url == expected for url in df["_source_url"].to_list())


class TestPartidoMembrosExtractor(BasePartidoChildTest):
    extractor_cls = PartidoMembrosExtractor
    route_suffix = "membros"


class TestPartidoLideresExtractor(BasePartidoChildTest):
    extractor_cls = PartidoLideresExtractor
    route_suffix = "lideres"
