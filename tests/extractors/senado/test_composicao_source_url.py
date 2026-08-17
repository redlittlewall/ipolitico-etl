"""
Testes de _source_url nos extratores de composição do Senado.
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.senado.api.composicao import (
    BlocosSenadoExtractor,
    LiderancasSenadoExtractor,
    MesaCongressoExtractor,
    MesaSenadoExtractor,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.BASE_URL = "https://legis.senado.leg.br/dadosabertos"
    return client


class TestBlocosSourceUrl:
    """Testes para BlocosSenadoExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_blocos_source_url(self, mock_client):
        """_source_url deve conter composicao/lista/blocos."""
        mock_client.fetch.return_value = {
            "ListaBlocoParlamentar": {
                "Blocos": {
                    "Bloco": [{"CodigoBloco": 1, "NomeBloco": "Bloco A"}],
                },
            },
        }
        ext = BlocosSenadoExtractor(mock_client)
        df = await ext.extract()

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert "composicao/lista/blocos" in url

    @pytest.mark.asyncio
    async def test_blocos_vazio(self, mock_client):
        """Resposta vazia retorna DataFrame vazio."""
        mock_client.fetch.return_value = {}
        ext = BlocosSenadoExtractor(mock_client)
        df = await ext.extract()

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestLiderancasSourceUrl:
    """Testes para LiderancasSenadoExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_liderancas_source_url(self, mock_client):
        """_source_url deve conter composicao/lideranca."""
        mock_client.fetch.return_value = [
            {"codigoParlamentar": 100, "nome": "Líder X"},
        ]
        ext = LiderancasSenadoExtractor(mock_client)
        df = await ext.extract()

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert "composicao/lideranca" in url

    @pytest.mark.asyncio
    async def test_liderancas_vazio(self, mock_client):
        """Resposta vazia retorna DataFrame vazio."""
        mock_client.fetch.return_value = []
        ext = LiderancasSenadoExtractor(mock_client)
        df = await ext.extract()

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestMesaSenadoSourceUrl:
    """Testes para MesaSenadoExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_mesa_senado_source_url(self, mock_client):
        """_source_url deve conter composicao/mesaSF."""
        mock_client.fetch.return_value = {
            "MesaSenado": {
                "Colegiados": {
                    "Colegiado": [
                        {
                            "CodigoColegiado": 1,
                            "Cargos": {
                                "Cargo": [{"Cargo": ["Presidente"]}],
                            },
                        },
                    ],
                },
            },
        }
        ext = MesaSenadoExtractor(mock_client)
        df = await ext.extract()

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        assert "composicao/mesaSF" in df["_source_url"][0]


class TestMesaCongressoSourceUrl:
    """Testes para MesaCongressoExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_mesa_congresso_source_url(self, mock_client):
        """_source_url deve conter composicao/mesaCN."""
        mock_client.fetch.return_value = {
            "MesaCongresso": {
                "Colegiados": {
                    "Colegiado": [
                        {
                            "CodigoColegiado": 1,
                            "Cargos": {
                                "Cargo": [{"Cargo": ["Presidente"]}],
                            },
                        },
                    ],
                },
            },
        }
        ext = MesaCongressoExtractor(mock_client)
        df = await ext.extract()

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        assert "composicao/mesaCN" in df["_source_url"][0]

    @pytest.mark.asyncio
    async def test_mesa_congresso_vazio(self, mock_client):
        """Resposta vazia retorna DataFrame vazio."""
        mock_client.fetch.return_value = {}
        ext = MesaCongressoExtractor(mock_client)
        df = await ext.extract()

        assert df.is_empty()
        assert "_source_url" not in df.columns
