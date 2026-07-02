"""
Testes de _source_url nos extratores de comissões do Senado.
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.senado.api.comissoes import (
    SenadoComissoesDetalheExtractor,
    SenadoComissoesListaExtractor,
    SenadoComissoesMembrosExtractor,
    SenadoComissoesReunioesExtractor,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.BASE_URL = "https://legis.senado.leg.br/dadosabertos"
    return client


class TestComissoesListaSourceUrl:
    """Testes para SenadoComissoesListaExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_comissoes_lista_source_url(self, mock_client):
        """_source_url deve conter comissao/lista/colegiados."""
        mock_client.fetch.return_value = {
            "ListaColegiados": {
                "Colegiados": {
                    "Colegiado": [{"Codigo": 1, "Sigla": "CCJ"}],
                },
            },
        }
        ext = SenadoComissoesListaExtractor(mock_client)
        df = await ext.extract()

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert "comissao/lista/colegiados" in url

    @pytest.mark.asyncio
    async def test_comissoes_lista_vazio(self, mock_client):
        """Resposta vazia retorna DataFrame vazio."""
        mock_client.fetch.return_value = {}
        ext = SenadoComissoesListaExtractor(mock_client)
        df = await ext.extract()

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestComissoesDetalheSourceUrl:
    """Testes para SenadoComissoesDetalheExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_comissoes_detalhe_source_url(self, mock_client):
        """_source_url deve conter comissao/{codigo}."""
        mock_client.fetch.return_value = {
            "ComissoesCongressoNacional": {
                "Colegiados": {
                    "Colegiado": [{"CodigoColegiado": 38}],
                },
            },
        }
        ext = SenadoComissoesDetalheExtractor(mock_client)
        df = await ext.extract(entity_ids=[38])

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        assert "comissao/38" in df["_source_url"][0]

    @pytest.mark.asyncio
    async def test_comissoes_detalhe_vazio(self, mock_client):
        """entity_ids vazio retorna DataFrame vazio."""
        ext = SenadoComissoesDetalheExtractor(mock_client)
        df = await ext.extract(entity_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestComissoesReunioesSourceUrl:
    """Testes para SenadoComissoesReunioesExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_comissoes_reunioes_source_url(self, mock_client):
        """_source_url deve conter comissao/agenda/{inicio}/{fim}."""
        mock_client.fetch.return_value = {
            "AgendaReuniao": {
                "reunioes": {
                    "reuniao": [{"codigo": 123}],
                },
            },
        }
        ext = SenadoComissoesReunioesExtractor(mock_client)
        df = await ext.extract(start_date="2025-06-01", end_date="2025-06-30")

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert "comissao/agenda/20250601/20250630" in url

    @pytest.mark.asyncio
    async def test_comissoes_reunioes_vazio(self, mock_client):
        """Sem datas retorna DataFrame vazio."""
        ext = SenadoComissoesReunioesExtractor(mock_client)
        df = await ext.extract(start_date=None, end_date=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestComissoesMembrosSourceUrl:
    """Testes para SenadoComissoesMembrosExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_comissoes_membros_source_url(self, mock_client):
        """_source_url deve conter composicao/comissao/{codigo}."""
        mock_client.fetch.return_value = {
            "ComposicaoAtivaComissaoSf": {
                "ComposicaoComissao": {
                    "IdentificacaoComissao": [{"CodigoComissao": 38}],
                    "Membros": {
                        "Membro": [{"nome": "Senador X"}],
                    },
                },
            },
        }
        ext = SenadoComissoesMembrosExtractor(mock_client)
        df = await ext.extract(entity_ids=[38])

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        assert "composicao/comissao/38" in df["_source_url"][0]

    @pytest.mark.asyncio
    async def test_comissoes_membros_vazio(self, mock_client):
        """entity_ids vazio retorna DataFrame vazio."""
        ext = SenadoComissoesMembrosExtractor(mock_client)
        df = await ext.extract(entity_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns
