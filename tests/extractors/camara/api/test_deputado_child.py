"""Testes para extratores de rotas filhas de /deputados/{id}/<suffix>."""

from unittest.mock import AsyncMock

import polars as pl
import pytest
from ipolitico.extractors.camara.api.deputado_child import MandatosExternosExtractor


@pytest.fixture
def extractor() -> MandatosExternosExtractor:
    ext = MandatosExternosExtractor(client=AsyncMock())
    ext.extract_child_route = AsyncMock()
    return ext


class TestMandatosExternosExtractor:
    """Testes do MandatosExternosExtractor (rota /deputados/{id}/mandatosExternos)."""

    def test_route_suffix(self):
        """route_suffix deve ser 'mandatosExternos'."""
        assert MandatosExternosExtractor.route_suffix == "mandatosExternos"

    @pytest.mark.asyncio
    async def test_extract_chama_route_correta(self, extractor: MandatosExternosExtractor):
        """extract(deputado_id=123) deve chamar extract_child_route com 'mandatosExternos'."""
        extractor.extract_child_route.return_value = pl.DataFrame(
            {"anoInicio": [2018], "cargo": ["Vereador"]}
        )

        df = await extractor.extract(deputado_id=123)

        assert df.height == 1
        extractor.extract_child_route.assert_called_once_with(123, "mandatosExternos")

    @pytest.mark.asyncio
    async def test_extract_adiciona_id_deputado(self, extractor: MandatosExternosExtractor):
        """Cada registro deve receber o id_deputado do pai."""
        extractor.extract_child_route.return_value = pl.DataFrame(
            {"anoInicio": [2018], "cargo": ["Vereador"]}
        )

        df = await extractor.extract(deputado_id=456)

        assert "id_deputado" in df.columns
        assert df["id_deputado"][0] == 456

    @pytest.mark.asyncio
    async def test_extract_sem_id_retorna_vazio(self, extractor: MandatosExternosExtractor):
        """extract(deputado_id=None) deve retornar DataFrame vazio."""
        df = await extractor.extract(deputado_id=None)

        assert isinstance(df, pl.DataFrame)
        assert df.is_empty()
        extractor.extract_child_route.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_resposta_vazia_retorna_vazio(self, extractor: MandatosExternosExtractor):
        """Se a API retornar lista vazia, retorna DataFrame vazio."""
        extractor.extract_child_route.return_value = pl.DataFrame()

        df = await extractor.extract(deputado_id=789)

        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_multiplos_mandatos(self, extractor: MandatosExternosExtractor):
        """Deputado com múltiplos mandatos externos retorna todos."""
        extractor.extract_child_route.return_value = pl.DataFrame(
            {
                "anoInicio": [2008, 2012, 2016],
                "cargo": ["Vereador", "Prefeito", "Deputado Estadual"],
            }
        )

        df = await extractor.extract(deputado_id=1)

        assert df.height == 3
        assert df["id_deputado"].to_list() == [1, 1, 1]
