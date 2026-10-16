"""Testes para os extratores da API v3 da Fatia 4 (Despesas, Empenhos e Pagamentos).

Testa:
- PortalDespesasEmpenhosApiExtractor (ENDPOINT = "api-de-dados/despesas/documentos", fase=1)
- PortalDespesasPagamentosApiExtractor (ENDPOINT = "api-de-dados/despesas/documentos", fase=3)
"""

from unittest.mock import AsyncMock
import pytest

from ipolitico.core.config import PORTAL_API_BASE_URL
from ipolitico.extractors.portal_transparencia.api.despesas_empenhos_extractor import (
    PortalDespesasEmpenhosApiExtractor,
)
from ipolitico.extractors.portal_transparencia.api.despesas_pagamentos_extractor import (
    PortalDespesasPagamentosApiExtractor,
)

API_BASE = PORTAL_API_BASE_URL.rstrip("/")


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.BASE_URL = PORTAL_API_BASE_URL
    return client


class TestPortalDespesasEmpenhosApiExtractor:
    def test_endpoint(self):
        assert PortalDespesasEmpenhosApiExtractor.ENDPOINT == "api-de-dados/despesas/documentos"

    @pytest.mark.asyncio
    async def test_extract_pagination_and_fase(self, mock_client):
        page1 = [{"documento": f"2024NE0000{i:02d}", "fase": "Empenho"} for i in range(1, 16)]
        page2 = [{"documento": f"2024NE0000{i:02d}", "fase": "Empenho"} for i in range(16, 21)]

        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/despesas/documentos"
            assert params["fase"] == 1
            assert params["dataEmissao"] == "15/01/2024"
            page = (params or {}).get("pagina", 1)
            return page1 if page == 1 else (page2 if page == 2 else [])

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalDespesasEmpenhosApiExtractor(mock_client)
        result = await extractor.extract(dataEmissao="15/01/2024")

        assert result.height == 20
        assert result["documento"].to_list() == [f"2024NE0000{i:02d}" for i in range(1, 21)]
        assert "fase=1" in result["_source_url"][0]

    @pytest.mark.asyncio
    async def test_extract_empty(self, mock_client):
        mock_client.fetch.return_value = []
        extractor = PortalDespesasEmpenhosApiExtractor(mock_client)
        result = await extractor.extract(dataEmissao="01/01/2024")
        assert result.is_empty()


class TestPortalDespesasPagamentosApiExtractor:
    def test_endpoint(self):
        assert PortalDespesasPagamentosApiExtractor.ENDPOINT == "api-de-dados/despesas/documentos"

    @pytest.mark.asyncio
    async def test_extract_pagination_and_fase(self, mock_client):
        page1 = [{"documento": f"2024OB8000{i:02d}", "fase": "Pagamento"} for i in range(1, 16)]
        page2 = [{"documento": "2024OB800016", "fase": "Pagamento"}]

        async def fake_fetch(endpoint, params=None):
            assert endpoint == "api-de-dados/despesas/documentos"
            assert params["fase"] == 3
            assert params["dataEmissao"] == "20/02/2024"
            assert params["unidadeGestora"] == "250001"
            page = (params or {}).get("pagina", 1)
            return page1 if page == 1 else (page2 if page == 2 else [])

        mock_client.fetch.side_effect = fake_fetch
        extractor = PortalDespesasPagamentosApiExtractor(mock_client)
        result = await extractor.extract(dataEmissao="20/02/2024", unidadeGestora="250001")

        assert result.height == 16
        assert result["documento"].to_list() == [f"2024OB8000{i:02d}" for i in range(1, 17)]
        assert "fase=3" in result["_source_url"][0]
        assert "unidadeGestora=250001" in result["_source_url"][0]

    @pytest.mark.asyncio
    async def test_extract_empty(self, mock_client):
        mock_client.fetch.return_value = []
        extractor = PortalDespesasPagamentosApiExtractor(mock_client)
        result = await extractor.extract(dataEmissao="01/01/2024")
        assert result.is_empty()
