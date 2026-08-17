"""
Testes de _source_url nos extratores do Senado (Issue 05).

Usa AsyncMock no client.fetch para testes rápidos e isolados,
padrão usado nos testes de _source_url da Câmara.
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.senado.api.senadores import SenadoSenadoresExtractor


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.BASE_URL = "https://legis.senado.leg.br/dadosabertos"
    return client


class TestSenadoSenadoresSourceUrl:
    """Tracer bullet: SenadoSenadoresExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_senadores_source_url_por_legislatura(self, mock_client):
        """_source_url deve conter senador/lista/legislatura/{id}."""
        mock_client.fetch.return_value = {
            "ListaParlamentarLegislatura": {
                "Parlamentares": {
                    "Parlamentar": [
                        {"IdentificacaoParlamentar": {"CodigoParlamentar": "5918"}},
                    ],
                },
            },
        }
        ext = SenadoSenadoresExtractor(mock_client)
        df = await ext.extract(legislatura_id=57)

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://legis.senado.leg.br/dadosabertos")
        assert "senador/lista/legislatura/57" in url

    @pytest.mark.asyncio
    async def test_senadores_source_url_atual(self, mock_client):
        """_source_url deve conter senador/lista/atual."""
        mock_client.fetch.return_value = {
            "ListaParlamentarEmExercicio": {
                "Parlamentares": {
                    "Parlamentar": [
                        {"IdentificacaoParlamentar": {"CodigoParlamentar": "5672"}},
                    ],
                },
            },
        }
        ext = SenadoSenadoresExtractor(mock_client)
        df = await ext.extract()

        assert not df.is_empty()
        assert "_source_url" in df.columns
        url = df["_source_url"][0]
        assert "senador/lista/atual" in url

    @pytest.mark.asyncio
    async def test_senadores_source_url_vazio(self, mock_client):
        """DataFrame vazio retornado sem _source_url."""
        mock_client.fetch.return_value = {"ListaParlamentarLegislatura": {}}
        ext = SenadoSenadoresExtractor(mock_client)
        df = await ext.extract(legislatura_id=99)

        assert df.is_empty()
        assert "_source_url" not in df.columns
