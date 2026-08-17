"""
Testes de _source_url nos extratores Senado que são filhos de senador
e possuem CodigoParlamentar como coluna flat (mandatos, filiacoes).
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.senado.api.senadores import (
    SenadoFiliacoesExtractor,
    SenadoMandatosExtractor,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.BASE_URL = "https://legis.senado.leg.br/dadosabertos"
    return client


class TestSenadoMandatosSourceUrl:
    """Testes para SenadoMandatosExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_mandatos_source_url(self, mock_client):
        """_source_url deve conter senador/{codigo}/mandatos."""
        mock_client.fetch.return_value = {
            "MandatoParlamentar": {
                "Parlamentar": {
                    "Codigo": 5918,
                    "Mandatos": {
                        "Mandato": [
                            {"CodigoMandato": "526", "UfParlamentar": "PE"},
                        ],
                    },
                },
            },
        }
        ext = SenadoMandatosExtractor(mock_client)
        df = await ext.extract(codigo=5918)

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        assert df["_source_url"][0].startswith("https://legis.senado.leg.br/dadosabertos")
        assert "senador/5918/mandatos" in df["_source_url"][0]

    @pytest.mark.asyncio
    async def test_mandatos_source_url_vazio(self, mock_client):
        """Mandatos sem codigo retorna DataFrame vazio."""
        ext = SenadoMandatosExtractor(mock_client)
        df = await ext.extract(codigo=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestSenadoFiliacoesSourceUrl:
    """Testes para SenadoFiliacoesExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_filiacoes_source_url(self, mock_client):
        """_source_url deve conter senador/{codigo}/filiacoes."""
        mock_client.fetch.return_value = {
            "FiliacaoParlamentar": {
                "Parlamentar": {
                    "Codigo": 5918,
                    "Filiacoes": {
                        "Filiacao": [
                            {"Partido": {"SiglaPartido": "PT"}},
                        ],
                    },
                },
            },
        }
        ext = SenadoFiliacoesExtractor(mock_client)
        df = await ext.extract(codigo=5918)

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://legis.senado.leg.br/dadosabertos")
        assert "senador/5918/filiacoes" in url

    @pytest.mark.asyncio
    async def test_filiacoes_source_url_vazio(self, mock_client):
        """Filiacoes sem codigo retorna DataFrame vazio."""
        ext = SenadoFiliacoesExtractor(mock_client)
        df = await ext.extract(codigo=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns
