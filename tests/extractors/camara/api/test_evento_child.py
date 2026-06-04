"""Testes para extratores de rotas filhas de /eventos/{id}/<suffix>."""

from unittest.mock import AsyncMock

import polars as pl
import pytest
from ipolitico.extractors.camara.api.evento_child import EventoOrgaosExtractor


@pytest.fixture
def extractor() -> EventoOrgaosExtractor:
    client = AsyncMock()
    ext = EventoOrgaosExtractor(client)
    ext.fetch_unpaginated = AsyncMock()
    return ext


class TestEventoOrgaosExtractor:
    """Testes do EventoOrgaosExtractor (rota /eventos/{id}/orgaos)."""

    def test_route_suffix(self):
        """route_suffix deve ser 'orgaos'."""
        assert EventoOrgaosExtractor.route_suffix == "orgaos"

    def test_parent_id_field(self):
        """parent_id_field deve ser 'id_evento'."""
        assert EventoOrgaosExtractor.parent_id_field == "id_evento"

    @pytest.mark.asyncio
    async def test_extract_chama_endpoint_para_cada_evento(self, extractor: EventoOrgaosExtractor):
        """extract([1, 2]) deve chamar /eventos/1/orgaos e /eventos/2/orgaos."""
        extractor.fetch_unpaginated.side_effect = [
            [{"id": 10, "sigla": "CD", "nome": "Comissão A"}],
            [{"id": 20, "sigla": "CE", "nome": "Comissão B"}],
        ]

        df = await extractor.extract(evento_ids=[1, 2])

        assert df.height == 2
        assert extractor.fetch_unpaginated.call_count == 2

        calls = extractor.fetch_unpaginated.call_args_list
        assert "eventos/1/orgaos" in calls[0][0][0]
        assert "eventos/2/orgaos" in calls[1][0][0]

    @pytest.mark.asyncio
    async def test_extract_adiciona_id_evento(self, extractor: EventoOrgaosExtractor):
        """Cada registro deve receber o id_evento do pai."""
        extractor.fetch_unpaginated.return_value = [
            {"id": 10, "sigla": "CD", "nome": "Comissão A"},
        ]

        df = await extractor.extract(evento_ids=[5])

        assert df.height == 1
        assert "id_evento" in df.columns
        assert df["id_evento"][0] == 5

    @pytest.mark.asyncio
    async def test_extract_sem_ids_retorna_vazio(self, extractor: EventoOrgaosExtractor):
        """extract(evento_ids=None) deve retornar DataFrame vazio."""
        df = await extractor.extract(evento_ids=None)

        assert isinstance(df, pl.DataFrame)
        assert df.is_empty()
        extractor.fetch_unpaginated.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_ignora_erro_em_um_evento(self, extractor: EventoOrgaosExtractor):
        """Se um evento falhar, o extrator continua com os demais."""
        extractor.fetch_unpaginated.side_effect = [
            [{"id": 10, "sigla": "CD", "nome": "Comissão A"}],
            Exception("API error"),
            [{"id": 30, "sigla": "CE", "nome": "Comissão C"}],
        ]

        df = await extractor.extract(evento_ids=[1, 2, 3])

        assert df.height == 2
        assert extractor.fetch_unpaginated.call_count == 3

    @pytest.mark.asyncio
    async def test_extract_evento_sem_orgaos_retorna_vazio_se_lista_unica(
        self, extractor: EventoOrgaosExtractor
    ):
        """Se o evento não tiver órgãos, retorna lista vazia para ele (agrega geral vazio)."""
        extractor.fetch_unpaginated.side_effect = [
            [],
            [{"id": 20, "sigla": "CE", "nome": "Comissão B"}],
        ]

        df = await extractor.extract(evento_ids=[1, 2])

        assert df.height == 1
        assert df["id_evento"][0] == 2
