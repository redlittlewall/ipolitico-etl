"""
Testes de _source_url nos extratores de processos do Senado.
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.senado.api.processos import (
    SenadoProcessosDetalheExtractor,
    SenadoProcessosDocumentosExtractor,
    SenadoProcessosEmendasExtractor,
    SenadoProcessosExtractor,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.BASE_URL = "https://legis.senado.leg.br/dadosabertos"
    return client


class TestSenadoProcessosSourceUrl:
    """Testes para SenadoProcessosExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_processos_source_url(self, mock_client):
        """_source_url deve conter processo."""
        mock_client.fetch.return_value = [{"id": 123, "descricao": "PL 123"}]
        ext = SenadoProcessosExtractor(mock_client)
        df = await ext.extract()

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert "processo" in df["_source_url"][0]

    @pytest.mark.asyncio
    async def test_processos_source_url_vazio(self, mock_client):
        """Resposta vazia retorna DataFrame vazio."""
        mock_client.fetch.return_value = None
        ext = SenadoProcessosExtractor(mock_client)
        df = await ext.extract()

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestSenadoProcessosDetalheSourceUrl:
    """Testes para SenadoProcessosDetalheExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_processos_detalhe_source_url(self, mock_client):
        """_source_url deve conter processo/{id}."""
        mock_client.fetch.return_value = {"id": 456, "descricao": "PL 456"}
        ext = SenadoProcessosDetalheExtractor(mock_client)
        df = await ext.extract(entity_ids=[456])

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        assert "processo/456" in df["_source_url"][0]

    @pytest.mark.asyncio
    async def test_processos_detalhe_multiplos(self, mock_client):
        """Múltiplos entity_ids devem ter URLs distintas."""
        mock_client.fetch.side_effect = [
            {"id": 1, "descricao": "PL 1"},
            {"id": 2, "descricao": "PL 2"},
        ]
        ext = SenadoProcessosDetalheExtractor(mock_client)
        df = await ext.extract(entity_ids=[1, 2])

        assert df.height == 2
        assert "processo/1" in df["_source_url"][0]
        assert "processo/2" in df["_source_url"][1]

    @pytest.mark.asyncio
    async def test_processos_detalhe_vazio(self, mock_client):
        """entity_ids vazio retorna DataFrame vazio."""
        ext = SenadoProcessosDetalheExtractor(mock_client)
        df = await ext.extract(entity_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestSenadoProcessosEmendasSourceUrl:
    """Testes para SenadoProcessosEmendasExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_processos_emendas_source_url(self, mock_client):
        """_source_url deve conter processo/emenda com params."""
        mock_client.fetch.return_value = [{"id": 789, "tipo": "Emenda"}]
        ext = SenadoProcessosEmendasExtractor(mock_client)
        df = await ext.extract(start_date="2024-01-01", end_date="2024-01-31")

        assert not df.is_empty()
        assert "_source_url" in df.columns
        url = df["_source_url"][0]
        assert "processo/emenda" in url
        assert "dataInicio=2024-01-01" in url
        assert "dataFim=2024-01-31" in url

    @pytest.mark.asyncio
    async def test_processos_emendas_vazio(self, mock_client):
        """Sem datas retorna DataFrame vazio."""
        ext = SenadoProcessosEmendasExtractor(mock_client)
        df = await ext.extract(start_date=None, end_date=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestSenadoProcessosDocumentosSourceUrl:
    """Testes para SenadoProcessosDocumentosExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_processos_documentos_source_url(self, mock_client):
        """_source_url deve conter processo/documento com params."""
        mock_client.fetch.return_value = [{"id": 999, "tipo": "Documento"}]
        ext = SenadoProcessosDocumentosExtractor(mock_client)
        df = await ext.extract(start_date="2024-06-01", end_date="2024-06-30")

        assert not df.is_empty()
        assert "_source_url" in df.columns
        url = df["_source_url"][0]
        assert "processo/documento" in url
        assert "dataInicio=2024-06-01" in url
        assert "dataFim=2024-06-30" in url

    @pytest.mark.asyncio
    async def test_processos_documentos_vazio(self, mock_client):
        """Sem datas retorna DataFrame vazio."""
        ext = SenadoProcessosDocumentosExtractor(mock_client)
        df = await ext.extract(start_date=None, end_date=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns
