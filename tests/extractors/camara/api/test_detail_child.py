"""Tests for detail_child extractors (BlocosDetalheExtractor, ProposicoesDetalheExtractor)."""

from unittest.mock import AsyncMock

import polars as pl
import pytest
from ipolitico.extractors.camara.api.detail_child import (
    BlocosDetalheExtractor,
    DetailByIdExtractor,
    ProposicoesDetalheExtractor,
)


class TestBlocosDetalheExtractor:
    def test_base_route(self):
        """BlocosDetalheExtractor deve ter base_route = 'blocos'."""
        assert BlocosDetalheExtractor.base_route == "blocos"

    def test_eh_subclasse_de_detail_by_id(self):
        """BlocosDetalheExtractor deve herdar de DetailByIdExtractor."""
        assert issubclass(BlocosDetalheExtractor, DetailByIdExtractor)


class TestProposicoesDetalheExtractor:
    def test_base_route(self):
        """ProposicoesDetalheExtractor deve ter base_route = 'proposicoes'."""
        assert ProposicoesDetalheExtractor.base_route == "proposicoes"

    def test_eh_subclasse_de_detail_by_id(self):
        """ProposicoesDetalheExtractor deve herdar de DetailByIdExtractor."""
        assert issubclass(ProposicoesDetalheExtractor, DetailByIdExtractor)


@pytest.fixture
def mock_client():
    return AsyncMock()


class TestExtractBehavior:
    """Testa o comportamento de extract() dos extratores de detalhe."""

    @pytest.mark.asyncio
    async def test_blocos_detalhe_chama_endpoint_correto(self, mock_client):
        """extract([1, 2]) deve chamar /blocos/1 e /blocos/2."""
        mock_client.fetch.side_effect = [
            {"id": 1, "nome": "Bloco A"},
            {"id": 2, "nome": "Bloco B"},
        ]
        ext = BlocosDetalheExtractor(client=mock_client)

        result = await ext.extract(entity_ids=[1, 2])

        assert isinstance(result, pl.DataFrame)
        assert len(result) == 2
        assert mock_client.fetch.call_count == 2
        mock_client.fetch.assert_any_call("blocos/1")
        mock_client.fetch.assert_any_call("blocos/2")

    @pytest.mark.asyncio
    async def test_proposicoes_detalhe_chama_endpoint_correto(self, mock_client):
        """extract([257161]) deve chamar /proposicoes/257161."""
        mock_client.fetch.return_value = {
            "id": 257161,
            "siglaTipo": "PL",
            "numero": 123,
        }
        ext = ProposicoesDetalheExtractor(client=mock_client)

        result = await ext.extract(entity_ids=[257161])

        assert isinstance(result, pl.DataFrame)
        assert len(result) == 1
        mock_client.fetch.assert_called_once_with("proposicoes/257161")

    @pytest.mark.asyncio
    async def test_extract_sem_ids_retorna_vazio(self, mock_client):
        """extract(None) ou entity_ids=[] deve retornar DataFrame vazio."""
        ext = BlocosDetalheExtractor(client=mock_client)

        result = await ext.extract(entity_ids=None)

        assert isinstance(result, pl.DataFrame)
        assert result.is_empty()

    @pytest.mark.asyncio
    async def test_extract_ignora_erro_em_um_id(self, mock_client):
        """Se um ID falhar, o extrator continua com os demais."""
        mock_client.fetch.side_effect = [
            {"id": 1, "nome": "Bloco A"},
            Exception("API error"),
            {"id": 3, "nome": "Bloco C"},
        ]
        ext = BlocosDetalheExtractor(client=mock_client)

        result = await ext.extract(entity_ids=[1, 2, 3])

        assert len(result) == 2
        assert mock_client.fetch.call_count == 3
