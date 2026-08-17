"""Testes de _source_url para OrgaoChildRouteExtractor e suas subclasses."""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.camara.api.orgao_child import (
    OrgaoEventosExtractor,
    OrgaoMembrosExtractor,
    OrgaoVotacoesExtractor,
)


class BaseOrgaoChildTest:
    """Mixin com fixture e testes genéricos para subclasses de OrgaoChildRouteExtractor."""

    extractor_cls = None
    route_suffix = ""

    @pytest.fixture
    def extractor(self):
        ext = self.extractor_cls(client=AsyncMock())
        ext.base_url = "https://dadosabertos.camara.leg.br/api/v2"
        ext.fetch_unpaginated = AsyncMock()
        return ext

    @pytest.mark.asyncio
    async def test_extract_injects_source_url(self, extractor):
        extractor.fetch_unpaginated.return_value = [
            {"id": 1, "nome": "Membro A"},
        ]

        df = await extractor.extract(orgao_ids=[5])

        assert "_source_url" in df.columns
        expected = f"https://dadosabertos.camara.leg.br/api/v2/orgaos/5/{self.route_suffix}"
        assert df["_source_url"][0] == expected

    @pytest.mark.asyncio
    async def test_extract_sem_ids_retorna_vazio(self, extractor):
        df = await extractor.extract(orgao_ids=None)
        assert df.is_empty()
        extractor.fetch_unpaginated.assert_not_called()

    @pytest.mark.asyncio
    async def test_adiciona_id_orgao(self, extractor):
        extractor.fetch_unpaginated.return_value = [
            {"id": 1, "nome": "Membro A"},
        ]

        df = await extractor.extract(orgao_ids=[99])

        assert "id_orgao" in df.columns
        assert df["id_orgao"][0] == 99

    @pytest.mark.asyncio
    async def test_source_url_mesmo_para_todos_registros_mesmo_orgao(self, extractor):
        extractor.fetch_unpaginated.return_value = [
            {"id": 1, "nome": "Membro A"},
            {"id": 2, "nome": "Membro B"},
        ]

        df = await extractor.extract(orgao_ids=[5])

        assert all(
            url == f"https://dadosabertos.camara.leg.br/api/v2/orgaos/5/{self.route_suffix}"
            for url in df["_source_url"].to_list()
        )


class TestOrgaoMembrosExtractor(BaseOrgaoChildTest):
    extractor_cls = OrgaoMembrosExtractor
    route_suffix = "membros"


class TestOrgaoEventosExtractor(BaseOrgaoChildTest):
    extractor_cls = OrgaoEventosExtractor
    route_suffix = "eventos"


class TestOrgaoVotacoesExtractor(BaseOrgaoChildTest):
    extractor_cls = OrgaoVotacoesExtractor
    route_suffix = "votacoes"
