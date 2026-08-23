"""Testes para os extratores da API v3 da Fatia 3 (Convênios e Repasses).

Testa:
- PortalConveniosApiExtractor (ENDPOINT = "api-de-dados/convenios")
- PortalConveniosAditivosApiExtractor (ENDPOINT = "api-de-dados/convenios")
"""

from unittest.mock import AsyncMock
import pytest

from ipolitico.core.config import PORTAL_API_BASE_URL
from ipolitico.extractors.portal_transparencia.api.convenios_extractor import (
    PortalConveniosApiExtractor,
)
from ipolitico.extractors.portal_transparencia.api.convenios_aditivos_extractor import (
    PortalConveniosAditivosApiExtractor,
)

API_BASE = PORTAL_API_BASE_URL.rstrip("/")


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.BASE_URL = PORTAL_API_BASE_URL
    return client


class TestPortalConveniosApiExtractor:
    def test_endpoint(self):
        assert PortalConveniosApiExtractor.ENDPOINT == "api-de-dados/convenios"

    @pytest.mark.asyncio
    async def test_extract_pagination(self, mock_client):
        page1 = [{"id": i, "valor": 50000.0} for i in range(1, 16)]
        page2 = [{"id": i, "valor": 50000.0} for i in range(16, 21)]

        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/convenios"
            page = (params or {}).get("pagina", 1)
            return page1 if page == 1 else (page2 if page == 2 else [])

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalConveniosApiExtractor(mock_client)
        result = await extractor.extract()

        assert result.height == 20
        assert result["id"].to_list() == list(range(1, 21))
        assert (
            result["_source_url"].to_list()
            == [f"{API_BASE}/api-de-dados/convenios?pagina=1"] * 15
            + [f"{API_BASE}/api-de-dados/convenios?pagina=2"] * 5
        )

    @pytest.mark.asyncio
    async def test_extract_with_params(self, mock_client):
        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/convenios"
            assert params["codigoOrgao"] == "36000"
            assert params["uf"] == "MG"
            assert params["dataInicial"] == "01/01/2024"
            assert params["dataFinal"] == "31/12/2024"
            page = (params or {}).get("pagina", 1)
            return [{"id": 1, "valor": 100000.0}] if page == 1 else []

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalConveniosApiExtractor(mock_client)
        result = await extractor.extract(
            codigoOrgao="36000",
            uf="MG",
            dataInicial="01/01/2024",
            dataFinal="31/12/2024",
        )

        assert result.height == 1
        assert "codigoOrgao=36000" in result["_source_url"][0]
        assert "uf=MG" in result["_source_url"][0]

    @pytest.mark.asyncio
    async def test_extract_empty(self, mock_client):
        mock_client.fetch.return_value = []
        extractor = PortalConveniosApiExtractor(mock_client)
        result = await extractor.extract()
        assert result.is_empty()


class TestPortalConveniosAditivosApiExtractor:
    def test_endpoint(self):
        assert PortalConveniosAditivosApiExtractor.ENDPOINT == "api-de-dados/convenios"

    @pytest.mark.asyncio
    async def test_extract_pagination(self, mock_client):
        page1 = [{"idConvenio": i, "numero": f"TA-{i}"} for i in range(1, 16)]
        page2 = [{"idConvenio": 16, "numero": "TA-16"}]

        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/convenios"
            page = (params or {}).get("pagina", 1)
            return page1 if page == 1 else (page2 if page == 2 else [])

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalConveniosAditivosApiExtractor(mock_client)
        result = await extractor.extract()

        assert result.height == 16
        assert result["idConvenio"].to_list() == list(range(1, 17))

    @pytest.mark.asyncio
    async def test_extract_with_params(self, mock_client):
        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/convenios"
            assert params["numero"] == "899123"
            page = (params or {}).get("pagina", 1)
            return [{"idConvenio": 10, "numero": "TA-899123"}] if page == 1 else []

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalConveniosAditivosApiExtractor(mock_client)
        result = await extractor.extract(numero="899123")

        assert result.height == 1
        assert "numero=899123" in result["_source_url"][0]

    @pytest.mark.asyncio
    async def test_extract_empty(self, mock_client):
        mock_client.fetch.return_value = []
        extractor = PortalConveniosAditivosApiExtractor(mock_client)
        result = await extractor.extract()
        assert result.is_empty()
