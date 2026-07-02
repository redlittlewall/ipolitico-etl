"""
Testes de _source_url nos extratores de votações do Senado.
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.senado.api.orientacao_bancada import (
    SenadoOrientacaoBancadaExtractor,
)
from ipolitico.extractors.senado.api.votacoes_comissao import (
    SenadoVotacoesComissaoExtractor,
)
from ipolitico.extractors.senado.api.votacoes_senado import SenadoVotacoesExtractor
from ipolitico.extractors.senado.api.votos_senado import SenadoVotosExtractor


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.BASE_URL = "https://legis.senado.leg.br/dadosabertos"
    return client


class TestSenadoVotacoesSourceUrl:
    """Testes para SenadoVotacoesExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_votacoes_source_url(self, mock_client):
        """_source_url deve conter votacao?ano=YYYY."""
        mock_client.fetch.return_value = [
            {"codigoSessaoVotacao": "v1", "descricao": "Votação"},
        ]
        ext = SenadoVotacoesExtractor(mock_client)
        df = await ext.extract(year=2025)

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://legis.senado.leg.br/dadosabertos")
        assert "votacao" in url
        assert "ano=2025" in url

    @pytest.mark.asyncio
    async def test_votacoes_source_url_vazio(self, mock_client):
        """Resposta vazia retorna DataFrame vazio."""
        mock_client.fetch.return_value = None
        ext = SenadoVotacoesExtractor(mock_client)
        df = await ext.extract(year=2050)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestSenadoVotosSourceUrl:
    """Testes para SenadoVotosExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_votos_source_url(self, mock_client):
        """_source_url deve conter votacao?ano=YYYY."""
        mock_client.fetch.return_value = [
            {
                "codigoSessaoVotacao": "v1",
                "votos": [{"codigoParlamentar": "100"}],
            },
        ]
        ext = SenadoVotosExtractor(mock_client)
        df = await ext.extract(year=2025)

        assert not df.is_empty()
        assert "_source_url" in df.columns
        url = df["_source_url"][0]
        assert "votacao" in url
        assert "ano=2025" in url

    @pytest.mark.asyncio
    async def test_votos_source_url_vazio(self, mock_client):
        """Resposta vazia retorna DataFrame vazio."""
        mock_client.fetch.return_value = None
        ext = SenadoVotosExtractor(mock_client)
        df = await ext.extract(year=2050)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestSenadoVotacoesComissaoSourceUrl:
    """Testes para SenadoVotacoesComissaoExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_votacoes_comissao_source_url(self, mock_client):
        """_source_url deve conter votacaoComissao/comissao/{sigla}."""
        mock_client.fetch.return_value = [
            {"codigoSessaoVotacao": "vc1", "descricao": "Votação Comissão"},
        ]
        ext = SenadoVotacoesComissaoExtractor(mock_client)
        df = await ext.extract(sigla_comissao="CCJ")

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert "votacaoComissao/comissao/CCJ" in url

    @pytest.mark.asyncio
    async def test_votacoes_comissao_com_datas(self, mock_client):
        """_source_url deve incluir dataInicio/dataFim."""
        mock_client.fetch.return_value = [
            {"codigoSessaoVotacao": "vc2"},
        ]
        ext = SenadoVotacoesComissaoExtractor(mock_client)
        df = await ext.extract(
            sigla_comissao="CAE",
            start_date="2024-01-01",
            end_date="2024-06-30",
        )

        assert not df.is_empty()
        url = df["_source_url"][0]
        assert "votacaoComissao/comissao/CAE" in url
        assert "dataInicio=2024-01-01" in url
        assert "dataFim=2024-06-30" in url

    @pytest.mark.asyncio
    async def test_votacoes_comissao_vazio(self, mock_client):
        """Sem sigla retorna DataFrame vazio."""
        ext = SenadoVotacoesComissaoExtractor(mock_client)
        df = await ext.extract(sigla_comissao=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestSenadoOrientacaoBancadaSourceUrl:
    """Testes para SenadoOrientacaoBancadaExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_orientacao_bancada_source_url(self, mock_client):
        """_source_url deve conter orientacaoBancada/{inicio}/{fim}."""
        mock_client.fetch.return_value = {
            "votacoes": [{"codigoSessaoVotacao": "v1"}],
        }
        ext = SenadoOrientacaoBancadaExtractor(mock_client)
        df = await ext.extract(start_date="2024-03-01", end_date="2024-03-31")

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert "orientacaoBancada" in url
        assert "20240301" in url
        assert "20240331" in url

    @pytest.mark.asyncio
    async def test_orientacao_bancada_vazio(self, mock_client):
        """Sem datas retorna DataFrame vazio."""
        ext = SenadoOrientacaoBancadaExtractor(mock_client)
        df = await ext.extract(start_date=None, end_date=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns
