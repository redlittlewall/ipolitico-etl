"""
Testes de _source_url nos extratores Senado de detalhe e discursos.
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.senado.api.discursos import DiscursosSenadorExtractor
from ipolitico.extractors.senado.api.senadores_detalhe import (
    SenadoSenadoresDetalheExtractor,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.BASE_URL = "https://legis.senado.leg.br/dadosabertos"
    return client


class TestSenadoSenadoresDetalheSourceUrl:
    """Testes para SenadoSenadoresDetalheExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_detalhe_source_url(self, mock_client):
        """_source_url deve conter senador/{codigo}."""
        mock_client.fetch.return_value = {
            "DetalheParlamentar": {
                "Parlamentar": {
                    "IdentificacaoParlamentar": {"CodigoParlamentar": "5918"},
                },
            },
        }
        ext = SenadoSenadoresDetalheExtractor(mock_client)
        df = await ext.extract(entity_ids=[5918])

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://legis.senado.leg.br/dadosabertos")
        assert url.endswith("senador/5918")

    @pytest.mark.asyncio
    async def test_detalhe_source_url_multiplos(self, mock_client):
        """Múltiplos entity_ids devem ter URLs distintas."""
        mock_client.fetch.side_effect = [
            {
                "DetalheParlamentar": {
                    "Parlamentar": {
                        "IdentificacaoParlamentar": {"CodigoParlamentar": "5918"},
                    },
                },
            },
            {
                "DetalheParlamentar": {
                    "Parlamentar": {
                        "IdentificacaoParlamentar": {"CodigoParlamentar": "5672"},
                    },
                },
            },
        ]
        ext = SenadoSenadoresDetalheExtractor(mock_client)
        df = await ext.extract(entity_ids=[5918, 5672])

        assert df.height == 2
        assert "senador/5918" in df["_source_url"][0]
        assert "senador/5672" in df["_source_url"][1]

    @pytest.mark.asyncio
    async def test_detalhe_source_url_vazio(self, mock_client):
        """entity_ids vazio retorna DataFrame vazio."""
        ext = SenadoSenadoresDetalheExtractor(mock_client)
        df = await ext.extract(entity_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestDiscursosSenadorSourceUrl:
    """Testes para DiscursosSenadorExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_discursos_senador_source_url(self, mock_client):
        """_source_url deve conter senador/{codigo}/discursos."""
        mock_client.fetch.return_value = {
            "Parlamentar": {
                "IdentificacaoParlamentar": {"CodigoParlamentar": "5918"},
                "Pronunciamentos": {
                    "Pronunciamento": [{"codigo": "123"}],
                },
            },
        }
        ext = DiscursosSenadorExtractor(mock_client)
        df = await ext.extract(codigo=5918)

        assert not df.is_empty()
        assert "_source_url" in df.columns
        url = df["_source_url"][0]
        assert url.startswith("https://legis.senado.leg.br/dadosabertos")
        assert "senador/5918/discursos" in url

    @pytest.mark.asyncio
    async def test_discursos_senador_source_url_com_params(self, mock_client):
        """_source_url deve incluir dataInicio/dataFim."""
        mock_client.fetch.return_value = {
            "Parlamentar": {
                "Pronunciamentos": {
                    "Pronunciamento": [{"codigo": "456"}],
                },
            },
        }
        ext = DiscursosSenadorExtractor(mock_client)
        df = await ext.extract(codigo=5918, dataInicio="2024-01-01", dataFim="2024-06-30")

        assert not df.is_empty()
        url = df["_source_url"][0]
        assert "senador/5918/discursos" in url
        assert "dataInicio=2024-01-01" in url
        assert "dataFim=2024-06-30" in url

    @pytest.mark.asyncio
    async def test_discursos_senador_source_url_vazio(self, mock_client):
        """Sem codigo retorna DataFrame vazio."""
        ext = DiscursosSenadorExtractor(mock_client)
        df = await ext.extract(codigo=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns
