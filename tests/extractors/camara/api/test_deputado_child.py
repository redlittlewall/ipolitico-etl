"""Testes para extratores de rotas filhas de /deputados/{id}/<suffix>."""

from unittest.mock import AsyncMock

import polars as pl
import pytest

from ipolitico.extractors.camara.api.deputado_child import (
    DiscursosExtractor,
    FrentesDeputadoExtractor,
    HistoricoDeputadoExtractor,
    MandatosExternosExtractor,
    OcupacoesExtractor,
    ProfissoesExtractor,
)


@pytest.fixture
def extractor() -> MandatosExternosExtractor:
    ext = MandatosExternosExtractor(client=AsyncMock())
    ext.base_url = "https://dadosabertos.camara.leg.br/api/v2"
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


@pytest.fixture
def profissoes_extractor() -> ProfissoesExtractor:
    ext = ProfissoesExtractor(client=AsyncMock())
    ext.base_url = "https://dadosabertos.camara.leg.br/api/v2"
    ext.extract_child_route = AsyncMock()
    return ext


@pytest.fixture
def discursos_extractor() -> DiscursosExtractor:
    ext = DiscursosExtractor(client=AsyncMock())
    ext.base_url = "https://dadosabertos.camara.leg.br/api/v2"
    ext.extract_temporal_route = AsyncMock()
    return ext


class TestDiscursosExtractorSourceUrl:
    """Testes de _source_url no DiscursosExtractor (rota temporal)."""

    @pytest.mark.asyncio
    async def test_extract_injects_source_url_com_datas(
        self, discursos_extractor: DiscursosExtractor
    ):
        """_source_url deve conter dataInicio e dataFim."""
        discursos_extractor.extract_temporal_route.return_value = pl.DataFrame(
            {"dataHoraInicio": ["2026-01-15T10:00:00"], "teor": ["Discurso A"]}
        )

        df = await discursos_extractor.extract(
            deputado_id=42, start_date="2026-01-01", end_date="2026-12-31"
        )

        assert "_source_url" in df.columns
        expected = (
            "https://dadosabertos.camara.leg.br/api/v2/deputados/42/discursos"
            "?dataFim=2026-12-31&dataInicio=2026-01-01"
        )
        assert df["_source_url"][0] == expected

    @pytest.mark.asyncio
    async def test_extract_sem_params_retorna_vazio(self, discursos_extractor: DiscursosExtractor):
        """Sem deputado_id ou datas, retorna DataFrame vazio."""
        df = await discursos_extractor.extract(deputado_id=None)
        assert df.is_empty()

        df2 = await discursos_extractor.extract(deputado_id=42, start_date=None, end_date=None)
        assert df2.is_empty()

        discursos_extractor.extract_temporal_route.assert_not_called()


class TestProfissoesExtractorSourceUrl:
    """Testes de _source_url no ProfissoesExtractor (rota /deputados/{id}/profissoes)."""

    @pytest.mark.asyncio
    async def test_extract_injects_source_url_para_cada_registro(
        self, profissoes_extractor: ProfissoesExtractor
    ):
        """Cada registro deve ter _source_url apontando para /deputados/{id}/profissoes."""
        profissoes_extractor.extract_child_route.return_value = pl.DataFrame(
            {
                "codTipo": [1, 2],
                "titulo": ["Advogado", "Médico"],
            }
        )

        df = await profissoes_extractor.extract(deputado_id=42)

        assert "_source_url" in df.columns
        assert all(
            url == "https://dadosabertos.camara.leg.br/api/v2/deputados/42/profissoes"
            for url in df["_source_url"].to_list()
        )

    @pytest.mark.asyncio
    async def test_extract_source_url_com_id_deputado(
        self, profissoes_extractor: ProfissoesExtractor
    ):
        """_source_url deve refletir o deputado_id passado."""
        profissoes_extractor.extract_child_route.return_value = pl.DataFrame(
            {"codTipo": [1], "titulo": ["Advogado"]}
        )

        df = await profissoes_extractor.extract(deputado_id=123)

        assert (
            df["_source_url"][0]
            == "https://dadosabertos.camara.leg.br/api/v2/deputados/123/profissoes"
        )


class TestStaticChildRoutesSourceUrl:
    """Testa que todos os DeputadoChildRouteExtractor injetam _source_url."""

    @pytest.fixture(params=["profissoes", "ocupacoes", "frentes", "historico", "mandatosExternos"])
    def route_extractor(self, request):
        cls_map = {
            "profissoes": ProfissoesExtractor,
            "ocupacoes": OcupacoesExtractor,
            "frentes": FrentesDeputadoExtractor,
            "historico": HistoricoDeputadoExtractor,
            "mandatosExternos": MandatosExternosExtractor,
        }
        ext = cls_map[request.param](client=AsyncMock())
        ext.base_url = "https://dadosabertos.camara.leg.br/api/v2"
        ext.extract_child_route = AsyncMock()
        return ext, request.param

    @pytest.mark.asyncio
    async def test_todos_static_routes_injectam_source_url(self, route_extractor):
        ext, suffix = route_extractor
        ext.extract_child_route.return_value = pl.DataFrame({"dummy": [1]})

        df = await ext.extract(deputado_id=7)

        assert "_source_url" in df.columns
        expected = f"https://dadosabertos.camara.leg.br/api/v2/deputados/7/{suffix}"
        assert df["_source_url"][0] == expected
