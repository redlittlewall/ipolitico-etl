"""Testes para os extratores da API v3 da Fatia 1 (Sanções e Integridade).

Testa:
- PortalCeisApiExtractor (ENDPOINT = "api-de-dados/ceis")
- PortalCnepApiExtractor (ENDPOINT = "api-de-dados/cnep")
- PortalCepimApiExtractor (ENDPOINT = "api-de-dados/cepim")
- PortalCeafApiExtractor (ENDPOINT = "api-de-dados/ceaf")
- PortalAcordosLenienciaApiExtractor (ENDPOINT = "api-de-dados/acordos-leniencia")
"""

from unittest.mock import AsyncMock
import pytest

from ipolitico.core.config import PORTAL_API_BASE_URL
from ipolitico.extractors.portal_transparencia.api.ceis_extractor import PortalCeisApiExtractor
from ipolitico.extractors.portal_transparencia.api.cnep_extractor import PortalCnepApiExtractor
from ipolitico.extractors.portal_transparencia.api.cepim_extractor import PortalCepimApiExtractor
from ipolitico.extractors.portal_transparencia.api.ceaf_extractor import PortalCeafApiExtractor
from ipolitico.extractors.portal_transparencia.api.acordos_leniencia_extractor import (
    PortalAcordosLenienciaApiExtractor,
)

API_BASE = PORTAL_API_BASE_URL.rstrip("/")


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.BASE_URL = PORTAL_API_BASE_URL
    return client


class TestPortalCeisApiExtractor:
    def test_endpoint(self):
        assert PortalCeisApiExtractor.ENDPOINT == "api-de-dados/ceis"

    @pytest.mark.asyncio
    async def test_extract_pagination(self, mock_client):
        page1 = [{"id": i, "nome": f"EMPRESA {i}"} for i in range(1, 16)]
        page2 = [{"id": i, "nome": f"EMPRESA {i}"} for i in range(16, 21)]

        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/ceis"
            page = (params or {}).get("pagina", 1)
            return page1 if page == 1 else page2

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalCeisApiExtractor(mock_client)
        result = await extractor.extract()

        assert result.height == 20
        assert result["id"].to_list() == list(range(1, 21))
        assert (
            result["_source_url"].to_list()
            == [f"{API_BASE}/api-de-dados/ceis?pagina=1"] * 15 + [f"{API_BASE}/api-de-dados/ceis?pagina=2"] * 5
        )

    @pytest.mark.asyncio
    async def test_extract_empty(self, mock_client):
        mock_client.fetch.return_value = []
        extractor = PortalCeisApiExtractor(mock_client)
        result = await extractor.extract()
        assert result.is_empty()


class TestPortalCnepApiExtractor:
    def test_endpoint(self):
        assert PortalCnepApiExtractor.ENDPOINT == "api-de-dados/cnep"

    @pytest.mark.asyncio
    async def test_extract_pagination(self, mock_client):
        page1 = [{"id": i, "valorMulta": "100,00"} for i in range(1, 16)]
        page2 = [{"id": 16, "valorMulta": "200,00"}]

        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/cnep"
            page = (params or {}).get("pagina", 1)
            return page1 if page == 1 else page2

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalCnepApiExtractor(mock_client)
        result = await extractor.extract()

        assert result.height == 16
        assert result["id"].to_list() == list(range(1, 17))

    @pytest.mark.asyncio
    async def test_extract_empty(self, mock_client):
        mock_client.fetch.return_value = []
        extractor = PortalCnepApiExtractor(mock_client)
        result = await extractor.extract()
        assert result.is_empty()


class TestPortalCepimApiExtractor:
    def test_endpoint(self):
        assert PortalCepimApiExtractor.ENDPOINT == "api-de-dados/cepim"

    @pytest.mark.asyncio
    async def test_extract_pagination(self, mock_client):
        page1 = [{"id": i, "motivo": f"Motivo {i}"} for i in range(1, 16)]

        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/cepim"
            page = (params or {}).get("pagina", 1)
            return page1 if page == 1 else []

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalCepimApiExtractor(mock_client)
        result = await extractor.extract()

        assert result.height == 15
        assert result["id"].to_list() == list(range(1, 16))

    @pytest.mark.asyncio
    async def test_extract_empty(self, mock_client):
        mock_client.fetch.return_value = []
        extractor = PortalCepimApiExtractor(mock_client)
        result = await extractor.extract()
        assert result.is_empty()


class TestPortalCeafApiExtractor:
    def test_endpoint(self):
        assert PortalCeafApiExtractor.ENDPOINT == "api-de-dados/ceaf"

    @pytest.mark.asyncio
    async def test_extract_pagination(self, mock_client):
        page1 = [{"id": i, "cargoEfetivo": f"Cargo {i}"} for i in range(1, 16)]

        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/ceaf"
            page = (params or {}).get("pagina", 1)
            return page1 if page == 1 else []

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalCeafApiExtractor(mock_client)
        result = await extractor.extract()

        assert result.height == 15
        assert result["id"].to_list() == list(range(1, 16))

    @pytest.mark.asyncio
    async def test_extract_empty(self, mock_client):
        mock_client.fetch.return_value = []
        extractor = PortalCeafApiExtractor(mock_client)
        result = await extractor.extract()
        assert result.is_empty()


class TestPortalAcordosLenienciaApiExtractor:
    def test_endpoint(self):
        assert PortalAcordosLenienciaApiExtractor.ENDPOINT == "api-de-dados/acordos-leniencia"

    @pytest.mark.asyncio
    async def test_extract_pagination(self, mock_client):
        page1 = [{"id": i, "situacaoAcordo": "Cumprindo"} for i in range(1, 16)]

        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/acordos-leniencia"
            page = (params or {}).get("pagina", 1)
            return page1 if page == 1 else []

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalAcordosLenienciaApiExtractor(mock_client)
        result = await extractor.extract()

        assert result.height == 15
        assert result["id"].to_list() == list(range(1, 16))

    @pytest.mark.asyncio
    async def test_extract_empty(self, mock_client):
        mock_client.fetch.return_value = []
        extractor = PortalAcordosLenienciaApiExtractor(mock_client)
        result = await extractor.extract()
        assert result.is_empty()
