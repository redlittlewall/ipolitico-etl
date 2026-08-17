"""
Testes de _source_url nos extratores Câmara child/lista (Issue 03).

Cada extrator retorna listas sem ID único no registro, portanto a URL
de auditoria é a do endpoint chamado com os parâmetros usados.
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.camara.api.bloco_child import BlocoPartidosExtractor
from ipolitico.extractors.camara.api.deputado_child import (
    DiscursosExtractor,
    ProfissoesExtractor,
)
from ipolitico.extractors.camara.api.despesas import DespesasExtractor
from ipolitico.extractors.camara.api.detail_child import DeputadosDetalheExtractor
from ipolitico.extractors.camara.api.evento_child import (
    EventoDeputadosExtractor,
    EventoOrgaosExtractor,
    EventoPautaExtractor,
)
from ipolitico.extractors.camara.api.frente_child import FrenteMembrosExtractor
from ipolitico.extractors.camara.api.orgao_child import (
    OrgaoEventosExtractor,
    OrgaoMembrosExtractor,
    OrgaoVotacoesExtractor,
)
from ipolitico.extractors.camara.api.partido_child import (
    PartidoLideresExtractor,
    PartidoMembrosExtractor,
)
from ipolitico.extractors.camara.api.proposicao_child import (
    AutoresExtractor,
    ProposicoesVotacoesExtractor,
    RelacionadasExtractor,
    TemasExtractor,
    TramitacoesExtractor,
)
from ipolitico.extractors.camara.api.referencias import ReferenciasExtractor
from ipolitico.extractors.camara.api.votacao_child import OrientacoesExtractor


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.BASE_URL = "https://dadosabertos.camara.leg.br/api/v2"
    return client


class TestDespesasSourceUrl:
    """Tracer bullet: DespesasExtractor com e sem mês."""

    @pytest.mark.asyncio
    async def test_despesas_source_url_sem_mes(self, mock_client):
        """_source_url deve conter deputados/{id}/despesas?ano={year}."""
        mock_client.fetch.return_value = [
            {"tipoDespesa": "PASSAGEM", "valorLiquido": 500.0},
        ]
        ext = DespesasExtractor(client=mock_client)
        df = await ext.extract(deputado_id=42, year=2024)

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://dadosabertos.camara.leg.br")
        assert "deputados/42/despesas" in url
        assert "ano=2024" in url
        assert "mes" not in url

    @pytest.mark.asyncio
    async def test_despesas_source_url_com_mes(self, mock_client):
        """_source_url deve incluir mes quando fornecido."""
        mock_client.fetch.return_value = [
            {"tipoDespesa": "PASSAGEM", "valorLiquido": 300.0},
        ]
        ext = DespesasExtractor(client=mock_client)
        df = await ext.extract(deputado_id=7, year=2024, month=3)

        assert not df.is_empty()
        url = df["_source_url"][0]
        assert "deputados/7/despesas" in url
        assert "ano=2024" in url
        assert "mes=3" in url

    @pytest.mark.asyncio
    async def test_despesas_source_url_vazio(self, mock_client):
        """DataFrame vazio deve ser retornado sem _source_url."""
        mock_client.fetch.return_value = []
        ext = DespesasExtractor(client=mock_client)
        df = await ext.extract(deputado_id=99, year=2024)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestDeputadoChildSourceUrl:
    """Testes para Profissoes (rota estática) e Discursos (rota temporal)."""

    @pytest.mark.asyncio
    async def test_profissoes_source_url_rota_estatica(self, mock_client):
        """_source_url deve ser deputados/{id}/profissoes."""
        mock_client.fetch.return_value = [
            {"titulo": "Advogado", "entidade": "OAB"},
        ]
        ext = ProfissoesExtractor(client=mock_client)
        df = await ext.extract(deputado_id=42)

        assert not df.is_empty()
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://dadosabertos.camara.leg.br")
        assert "deputados/42/profissoes" in url

    @pytest.mark.asyncio
    async def test_profissoes_source_url_vazio(self, mock_client):
        """DataFrame vazio quando deputado_id é None."""
        ext = ProfissoesExtractor(client=mock_client)
        df = await ext.extract(deputado_id=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns

    @pytest.mark.asyncio
    async def test_discursos_source_url_temporal(self, mock_client):
        """_source_url deve incluir dataInicio e dataFim."""
        mock_client.fetch.return_value = [
            {"sumario": "Discurso importante", "uriEvento": "uri:1"},
        ]
        ext = DiscursosExtractor(client=mock_client)
        df = await ext.extract(
            deputado_id=42,
            start_date="2024-01-01",
            end_date="2024-06-30",
        )

        assert not df.is_empty()
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://dadosabertos.camara.leg.br")
        assert "deputados/42/discursos" in url
        assert "dataInicio=2024-01-01" in url
        assert "dataFim=2024-06-30" in url

    @pytest.mark.asyncio
    async def test_discursos_source_url_vazio(self, mock_client):
        """DataFrame vazio quando falta start_date."""
        ext = DiscursosExtractor(client=mock_client)
        df = await ext.extract(deputado_id=42, start_date=None, end_date=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestProposicaoChildSourceUrl:
    """Testes para Tramitacoes, Autores, Relacionadas, Temas, ProposicoesVotacoes."""

    @pytest.mark.asyncio
    async def test_tramitacoes_source_url(self, mock_client):
        """_source_url deve conter proposicoes/{id}/tramitacoes."""
        mock_client.fetch.side_effect = [
            [{"sequencia": 1, "dataHora": "2024-01-01T00:00:00"}],
        ]
        ext = TramitacoesExtractor(client=mock_client)
        df = await ext.extract(proposicao_ids=[123])

        assert not df.is_empty()
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://dadosabertos.camara.leg.br")
        assert "proposicoes/123/tramitacoes" in url

    @pytest.mark.asyncio
    async def test_autores_source_url(self, mock_client):
        """_source_url deve conter proposicoes/{id}/autores."""
        mock_client.fetch.side_effect = [
            [{"nome": "Autor X", "tipo": "Deputado"}],
        ]
        ext = AutoresExtractor(client=mock_client)
        df = await ext.extract(proposicao_ids=[456])

        assert not df.is_empty()
        url = df["_source_url"][0]
        assert "proposicoes/456/autores" in url

    @pytest.mark.asyncio
    async def test_relacionadas_source_url(self, mock_client):
        """_source_url deve conter proposicoes/{id}/relacionadas."""
        mock_client.fetch.side_effect = [
            [{"id": 789, "siglaTipo": "PL"}],
        ]
        ext = RelacionadasExtractor(client=mock_client)
        df = await ext.extract(proposicao_ids=[101])

        assert not df.is_empty()
        url = df["_source_url"][0]
        assert "proposicoes/101/relacionadas" in url

    @pytest.mark.asyncio
    async def test_temas_source_url(self, mock_client):
        """_source_url deve conter proposicoes/{id}/temas."""
        mock_client.fetch.side_effect = [
            [{"tema": "Educação"}],
        ]
        ext = TemasExtractor(client=mock_client)
        df = await ext.extract(proposicao_ids=[202])

        assert not df.is_empty()
        url = df["_source_url"][0]
        assert "proposicoes/202/temas" in url

    @pytest.mark.asyncio
    async def test_proposicoes_votacoes_source_url(self, mock_client):
        """_source_url deve conter proposicoes/{id}/votacoes."""
        mock_client.fetch.side_effect = [
            [{"id": "v1", "descricao": "Votação"}],
        ]
        ext = ProposicoesVotacoesExtractor(client=mock_client)
        df = await ext.extract(proposicao_ids=[303])

        assert not df.is_empty()
        url = df["_source_url"][0]
        assert "proposicoes/303/votacoes" in url

    @pytest.mark.asyncio
    async def test_proposicao_child_vazio(self, mock_client):
        """DataFrame vazio quando proposicao_ids é None."""
        ext = TramitacoesExtractor(client=mock_client)
        df = await ext.extract(proposicao_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestOrgaoChildSourceUrl:
    """Testes para OrgaoMembros, OrgaoEventos, OrgaoVotacoes."""

    @pytest.mark.asyncio
    async def test_orgao_membros_source_url(self, mock_client):
        """_source_url deve conter orgaos/{id}/membros."""
        mock_client.fetch.side_effect = [
            [{"nome": "Membro X", "id": 1}],
        ]
        ext = OrgaoMembrosExtractor(client=mock_client)
        df = await ext.extract(orgao_ids=[50])

        assert not df.is_empty()
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://dadosabertos.camara.leg.br")
        assert "orgaos/50/membros" in url

    @pytest.mark.asyncio
    async def test_orgao_votacoes_source_url_com_data(self, mock_client):
        """_source_url deve incluir dataInicio/dataFim quando fornecidos."""
        mock_client.fetch.side_effect = [
            [{"id": "v1", "data": "2024-01-01"}],
        ]
        ext = OrgaoVotacoesExtractor(client=mock_client)
        df = await ext.extract(
            orgao_ids=[50],
            start_date="2024-01-01",
            end_date="2024-06-30",
        )

        assert not df.is_empty()
        url = df["_source_url"][0]
        assert "orgaos/50/votacoes" in url
        assert "dataInicio=2024-01-01" in url
        assert "dataFim=2024-06-30" in url

    @pytest.mark.asyncio
    async def test_orgao_child_vazio(self, mock_client):
        """DataFrame vazio quando orgao_ids é None."""
        ext = OrgaoEventosExtractor(client=mock_client)
        df = await ext.extract(orgao_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestEventoChildSourceUrl:
    """Testes para EventoDeputados, EventoVotacoes, EventoPauta, EventoOrgaos."""

    @pytest.mark.asyncio
    async def test_evento_deputados_source_url(self, mock_client):
        """_source_url deve conter eventos/{id}/deputados."""
        mock_client.fetch.side_effect = [
            [{"nome": "Dep X", "id": 1}],
        ]
        ext = EventoDeputadosExtractor(client=mock_client)
        df = await ext.extract(evento_ids=[99])

        assert not df.is_empty()
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://dadosabertos.camara.leg.br")
        assert "eventos/99/deputados" in url

    @pytest.mark.asyncio
    async def test_evento_orgaos_source_url(self, mock_client):
        """_source_url deve conter eventos/{id}/orgaos."""
        mock_client.fetch.side_effect = [
            [{"sigla": "CCJ", "nome": "Comissão"}],
        ]
        ext = EventoOrgaosExtractor(client=mock_client)
        df = await ext.extract(evento_ids=[77])

        assert not df.is_empty()
        url = df["_source_url"][0]
        assert "eventos/77/orgaos" in url

    @pytest.mark.asyncio
    async def test_evento_child_vazio(self, mock_client):
        """DataFrame vazio quando evento_ids é None."""
        ext = EventoPautaExtractor(client=mock_client)
        df = await ext.extract(evento_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestPartidoChildSourceUrl:
    """Testes para PartidoMembros, PartidoLideres."""

    @pytest.mark.asyncio
    async def test_partido_membros_source_url(self, mock_client):
        """_source_url deve conter partidos/{id}/membros."""
        mock_client.fetch.side_effect = [
            [{"nome": "Fulano", "id": 1}],
        ]
        ext = PartidoMembrosExtractor(client=mock_client)
        df = await ext.extract(partido_ids=[10])

        assert not df.is_empty()
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://dadosabertos.camara.leg.br")
        assert "partidos/10/membros" in url

    @pytest.mark.asyncio
    async def test_partido_membros_source_url_com_params(self, mock_client):
        """_source_url deve incluir dataInicio/dataFim quando fornecidos."""
        mock_client.fetch.side_effect = [
            [{"nome": "Ciclano", "id": 2}],
        ]
        ext = PartidoMembrosExtractor(client=mock_client)
        df = await ext.extract(
            partido_ids=[10],
            start_date="2023-01-01",
            end_date="2023-12-31",
        )

        assert not df.is_empty()
        url = df["_source_url"][0]
        assert "partidos/10/membros" in url
        assert "dataInicio=2023-01-01" in url
        assert "dataFim=2023-12-31" in url

    @pytest.mark.asyncio
    async def test_partido_child_vazio(self, mock_client):
        """DataFrame vazio quando partido_ids é None."""
        ext = PartidoLideresExtractor(client=mock_client)
        df = await ext.extract(partido_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns

    @pytest.mark.asyncio
    async def test_partido_lideres_source_url(self, mock_client):
        """_source_url deve conter partidos/{id}/lideres."""
        mock_client.fetch.side_effect = [
            [{"nome": "Líder", "titulo": "Presidente"}],
        ]
        ext = PartidoLideresExtractor(client=mock_client)
        df = await ext.extract(partido_ids=[10])

        assert not df.is_empty()
        url = df["_source_url"][0]
        assert "partidos/10/lideres" in url


class TestFrenteBlocoSourceUrl:
    """Testes para FrenteMembros e BlocoPartidos."""

    @pytest.mark.asyncio
    async def test_frente_membros_source_url(self, mock_client):
        """_source_url deve conter frentes/{id}/membros."""
        mock_client.fetch.side_effect = [
            [{"nome": "Membro X", "id": 1}],
        ]
        ext = FrenteMembrosExtractor(client=mock_client)
        df = await ext.extract(frente_ids=[5])

        assert not df.is_empty()
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://dadosabertos.camara.leg.br")
        assert "frentes/5/membros" in url

    @pytest.mark.asyncio
    async def test_frente_membros_vazio(self, mock_client):
        """DataFrame vazio quando frente_ids é None."""
        ext = FrenteMembrosExtractor(client=mock_client)
        df = await ext.extract(frente_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns

    @pytest.mark.asyncio
    async def test_bloco_partidos_source_url(self, mock_client):
        """_source_url deve conter blocos/{id}/partidos."""
        mock_client.fetch.side_effect = [
            [{"sigla": "PT", "nome": "Partido"}],
        ]
        ext = BlocoPartidosExtractor(client=mock_client)
        df = await ext.extract(bloco_ids=[3])

        assert not df.is_empty()
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://dadosabertos.camara.leg.br")
        assert "blocos/3/partidos" in url

    @pytest.mark.asyncio
    async def test_bloco_partidos_vazio(self, mock_client):
        """DataFrame vazio quando bloco_ids é None."""
        ext = BlocoPartidosExtractor(client=mock_client)
        df = await ext.extract(bloco_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestReferenciasSourceUrl:
    """Testes para ReferenciasExtractor."""

    @pytest.mark.asyncio
    async def test_referencias_source_url(self, mock_client):
        """_source_url deve conter o caminho da referência."""
        mock_client.fetch.side_effect = [
            [{"cod": "1", "nome": "Ativo"}],
        ]
        ext = ReferenciasExtractor(client=mock_client)
        df = await ext.extract(routes=["referencias/deputados/codSituacao"])

        assert not df.is_empty()
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://dadosabertos.camara.leg.br")
        assert "referencias/deputados/codSituacao" in url


class TestOrientacoesSourceUrl:
    """Testes para OrientacoesExtractor (usa source_url_format com resource_id)."""

    @pytest.mark.asyncio
    async def test_orientacoes_source_url(self, mock_client):
        """_source_url deve usar source_url_format com resource_id."""
        mock_client.fetch.side_effect = [
            [{"siglaPartidoBloco": "PT", "orientacaoVoto": "Sim"}],
        ]
        ext = OrientacoesExtractor(client=mock_client)
        df = await ext.extract(votacao_ids=["v123"])

        assert not df.is_empty()
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://dadosabertos.camara.leg.br")
        assert "votacoes/v123/orientacoes" in url

    @pytest.mark.asyncio
    async def test_orientacoes_vazio(self, mock_client):
        """DataFrame vazio quando votacao_ids é None."""
        ext = OrientacoesExtractor(client=mock_client)
        df = await ext.extract(votacao_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestDeputadoDetalheSourceUrl:
    """Testes para DeputadosDetalheExtractor (source_url_format, Issue 02)."""

    @pytest.mark.asyncio
    async def test_deputados_detalhe_source_url(self, mock_client):
        """_source_url deve usar source_url_format com resource_id."""
        mock_client.fetch.side_effect = [
            {"id": 42, "cpf": "000.000.000-00"},
        ]
        ext = DeputadosDetalheExtractor(client=mock_client)
        df = await ext.extract(entity_ids=[42])

        assert not df.is_empty()
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert url.startswith("https://dadosabertos.camara.leg.br")
        assert "deputados/42" in url
