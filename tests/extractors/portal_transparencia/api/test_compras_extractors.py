"""Testes para os extratores da API v3 da Fatia 2 (Compras Públicas).

Testa:
- PortalLicitacoesApiExtractor (ENDPOINT = "api-de-dados/licitacoes")
- PortalContratosApiExtractor (ENDPOINT = "api-de-dados/contratos")
- PortalContratosAditivosApiExtractor (ENDPOINT = "api-de-dados/contratos/termo-aditivo")
"""

from unittest.mock import AsyncMock
import pytest

from ipolitico.core.config import PORTAL_API_BASE_URL
from ipolitico.extractors.portal_transparencia.api.licitacoes_extractor import (
    PortalLicitacoesApiExtractor,
)
from ipolitico.extractors.portal_transparencia.api.contratos_extractor import (
    PortalContratosApiExtractor,
)
from ipolitico.extractors.portal_transparencia.api.contratos_aditivos_extractor import (
    PortalContratosAditivosApiExtractor,
)

API_BASE = PORTAL_API_BASE_URL.rstrip("/")


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.BASE_URL = PORTAL_API_BASE_URL
    return client


class TestPortalLicitacoesApiExtractor:
    def test_endpoint(self):
        assert PortalLicitacoesApiExtractor.ENDPOINT == "api-de-dados/licitacoes"

    @pytest.mark.asyncio
    async def test_extract_pagination(self, mock_client):
        page1 = [{"id": i, "valor": 1000.0} for i in range(1, 16)]
        page2 = [{"id": i, "valor": 1000.0} for i in range(16, 21)]

        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/licitacoes"
            page = (params or {}).get("pagina", 1)
            return page1 if page == 1 else page2

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalLicitacoesApiExtractor(mock_client)
        result = await extractor.extract()

        assert result.height == 20
        assert result["id"].to_list() == list(range(1, 21))
        assert "codigoOrgao=26000" in result["_source_url"][0]
        assert "pagina=1" in result["_source_url"][0]
        assert "pagina=2" in result["_source_url"][15]

    @pytest.mark.asyncio
    async def test_extract_with_params(self, mock_client):
        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/licitacoes"
            assert params["codigoOrgao"] == "26000"
            assert params["dataInicial"] == "01/01/2024"
            assert params["dataFinal"] == "31/12/2024"
            return [{"id": 1, "valor": 500.0}] if params.get("pagina", 1) == 1 else []

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalLicitacoesApiExtractor(mock_client)
        result = await extractor.extract(
            codigoOrgao="26000",
            dataInicial="01/01/2024",
            dataFinal="31/12/2024",
        )

        assert result.height == 1
        assert "codigoOrgao=26000" in result["_source_url"][0]

    @pytest.mark.asyncio
    async def test_extract_empty(self, mock_client):
        mock_client.fetch.return_value = []
        extractor = PortalLicitacoesApiExtractor(mock_client)
        result = await extractor.extract()
        assert result.is_empty()


class TestPortalContratosApiExtractor:
    def test_endpoint(self):
        assert PortalContratosApiExtractor.ENDPOINT == "api-de-dados/contratos"

    @pytest.mark.asyncio
    async def test_extract_pagination(self, mock_client):
        page1 = [{"id": i, "numero": f"CT-{i}"} for i in range(1, 16)]
        page2 = [{"id": 16, "numero": "CT-16"}]

        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/contratos"
            page = (params or {}).get("pagina", 1)
            return page1 if page == 1 else page2

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalContratosApiExtractor(mock_client)
        result = await extractor.extract()

        assert result.height == 16
        assert result["id"].to_list() == list(range(1, 17))

    @pytest.mark.asyncio
    async def test_extract_with_params(self, mock_client):
        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/contratos"
            assert params["codigoOrgao"] == "30000"
            return [{"id": 10, "numero": "CT-10"}] if params.get("pagina", 1) == 1 else []

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalContratosApiExtractor(mock_client)
        result = await extractor.extract(codigoOrgao="30000")

        assert result.height == 1
        assert "codigoOrgao=30000" in result["_source_url"][0]

    @pytest.mark.asyncio
    async def test_extract_empty(self, mock_client):
        mock_client.fetch.return_value = []
        extractor = PortalContratosApiExtractor(mock_client)
        result = await extractor.extract()
        assert result.is_empty()


class TestPortalContratosAditivosApiExtractor:
    def test_endpoint(self):
        assert PortalContratosAditivosApiExtractor.ENDPOINT == "api-de-dados/contratos/termo-aditivo"

    @pytest.mark.asyncio
    async def test_extract_with_id(self, mock_client):
        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/contratos/termo-aditivo"
            assert params["id"] == 2002
            page = (params or {}).get("pagina", 1)
            return [{"id": 2002, "numero": "TA-01", "objetoAditivo": "Prorrogação"}] if page == 1 else []

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalContratosAditivosApiExtractor(mock_client)
        result = await extractor.extract(id=2002)

        assert result.height == 1
        assert result["numero"][0] == "TA-01"
        assert "id=2002" in result["_source_url"][0]

    @pytest.mark.asyncio
    async def test_extract_empty(self, mock_client):
        mock_client.fetch.return_value = []
        extractor = PortalContratosAditivosApiExtractor(mock_client)
        result = await extractor.extract(id=99999)
        assert result.is_empty()
