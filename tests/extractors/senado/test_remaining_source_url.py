"""
Testes de _source_url nos extratores restantes do Senado.
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.extractors.senado.api.discursos import (
    DiscursosPlenarioExtractor,
    DiscursosTextoExtractor,
    NotasTaquigrafiaReuniaoExtractor,
    NotasTaquigrafiaSessaoExtractor,
)
from ipolitico.extractors.senado.api.orcamento import (
    OrcamentoEmendasExtractor,
    OrcamentoOficiosExtractor,
)
from ipolitico.extractors.senado.api.plenario import (
    PlenarioAgendaExtractor,
    PlenarioResultadosExtractor,
    PlenarioSessoesExtractor,
)
from ipolitico.extractors.senado.api.vetos import (
    VetosDetalheExtractor,
    VetosPresidenciaisExtractor,
)


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.BASE_URL = "https://legis.senado.leg.br/dadosabertos"
    return client


class TestDiscursosPlenarioSourceUrl:
    """Testes para DiscursosPlenarioExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_discursos_plenario_source_url(self, mock_client):
        """_source_url deve conter plenario/lista/discursos/{inicio}/{fim}."""
        mock_client.fetch.return_value = [{"codigo": 1, "resumo": "Discurso"}]
        ext = DiscursosPlenarioExtractor(mock_client)
        df = await ext.extract(start_date="2024-01-01", end_date="2024-01-31")

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert "plenario/lista/discursos/20240101/20240131" in url

    @pytest.mark.asyncio
    async def test_discursos_plenario_vazio(self, mock_client):
        """Sem datas retorna DataFrame vazio."""
        ext = DiscursosPlenarioExtractor(mock_client)
        df = await ext.extract(start_date=None, end_date=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestDiscursosTextoSourceUrl:
    """Testes para DiscursosTextoExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_discursos_texto_source_url(self, mock_client):
        """_source_url deve conter discurso/texto-integral/{codigo}."""
        mock_client.fetch.return_value = {"codigo": 456, "texto": "..."}
        ext = DiscursosTextoExtractor(mock_client)
        df = await ext.extract(entity_ids=[456])

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert "discurso/texto-integral/456" in df["_source_url"][0]

    @pytest.mark.asyncio
    async def test_discursos_texto_vazio(self, mock_client):
        """entity_ids vazio retorna DataFrame vazio."""
        ext = DiscursosTextoExtractor(mock_client)
        df = await ext.extract(entity_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestNotasTaquigrafiaSessaoSourceUrl:
    """Testes para NotasTaquigrafiaSessaoExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_notas_sessao_source_url(self, mock_client):
        """_source_url deve conter taquigrafia/notas/sessao/{id}."""
        mock_client.fetch.return_value = {"idSessao": 789}
        ext = NotasTaquigrafiaSessaoExtractor(mock_client)
        df = await ext.extract(entity_ids=[789])

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert "taquigrafia/notas/sessao/789" in df["_source_url"][0]

    @pytest.mark.asyncio
    async def test_notas_sessao_vazio(self, mock_client):
        """entity_ids vazio retorna DataFrame vazio."""
        ext = NotasTaquigrafiaSessaoExtractor(mock_client)
        df = await ext.extract(entity_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestNotasTaquigrafiaReuniaoSourceUrl:
    """Testes para NotasTaquigrafiaReuniaoExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_notas_reuniao_source_url(self, mock_client):
        """_source_url deve conter taquigrafia/notas/reuniao/{id}."""
        mock_client.fetch.return_value = {"idReuniao": 321}
        ext = NotasTaquigrafiaReuniaoExtractor(mock_client)
        df = await ext.extract(entity_ids=[321])

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert "taquigrafia/notas/reuniao/321" in df["_source_url"][0]

    @pytest.mark.asyncio
    async def test_notas_reuniao_vazio(self, mock_client):
        """entity_ids vazio retorna DataFrame vazio."""
        ext = NotasTaquigrafiaReuniaoExtractor(mock_client)
        df = await ext.extract(entity_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestPlenarioAgendaSourceUrl:
    """Testes para PlenarioAgendaExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_plenario_agenda_source_url(self, mock_client):
        """_source_url deve conter plenario/agenda/dia/{data}."""
        mock_client.fetch.return_value = {
            "AgendaPlenario": {
                "Sessoes": {
                    "Sessao": [{"CodigoSessao": 1}],
                },
            },
        }
        ext = PlenarioAgendaExtractor(mock_client)
        df = await ext.extract(data="2024-07-01")

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert "plenario/agenda/dia/20240701" in url

    @pytest.mark.asyncio
    async def test_plenario_agenda_vazio(self, mock_client):
        """Sem data retorna DataFrame vazio."""
        ext = PlenarioAgendaExtractor(mock_client)
        df = await ext.extract(data=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestPlenarioResultadosSourceUrl:
    """Testes para PlenarioResultadosExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_plenario_resultados_source_url(self, mock_client):
        """_source_url deve conter plenario/resultado/{data}."""
        mock_client.fetch.return_value = {
            "ResultadoPlenario": {
                "Sessoes": {
                    "Sessao": [
                        {
                            "codigoSessao": 1,
                            "Itens": {
                                "Item": [{"codigoItem": 1}],
                            },
                        },
                    ],
                },
            },
        }
        ext = PlenarioResultadosExtractor(mock_client)
        df = await ext.extract(data="2024-07-01")

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert "plenario/resultado/20240701" in url

    @pytest.mark.asyncio
    async def test_plenario_resultados_vazio(self, mock_client):
        """Sem data retorna DataFrame vazio."""
        ext = PlenarioResultadosExtractor(mock_client)
        df = await ext.extract(data=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestPlenarioSessoesSourceUrl:
    """Testes para PlenarioSessoesExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_plenario_sessoes_source_url(self, mock_client):
        """_source_url deve conter plenario/legislatura/{data}."""
        mock_client.fetch.return_value = {
            "ListaLegislatura": {
                "Legislaturas": {
                    "Legislatura": [
                        {
                            "NumeroLegislatura": 57,
                            "SessoesLegislativas": {
                                "SessaoLegislativa": [{"CodigoSessao": 1}],
                            },
                        },
                    ],
                },
            },
        }
        ext = PlenarioSessoesExtractor(mock_client)
        df = await ext.extract(data="2024-07-01")

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert "plenario/legislatura/20240701" in url

    @pytest.mark.asyncio
    async def test_plenario_sessoes_vazio(self, mock_client):
        """Sem data retorna DataFrame vazio."""
        ext = PlenarioSessoesExtractor(mock_client)
        df = await ext.extract(data=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestOrcamentoEmendasSourceUrl:
    """Testes para OrcamentoEmendasExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_orcamento_emendas_source_url(self, mock_client):
        """_source_url deve conter orcamento/lista?ano=YYYY."""
        mock_client.fetch.return_value = {
            "ListaLoteEmendas": {
                "LotesEmendasOrcamento": {
                    "LoteEmendasOrcamento": [{"codigo": 1}],
                },
            },
        }
        ext = OrcamentoEmendasExtractor(mock_client)
        df = await ext.extract(ano=2025)

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert "orcamento/lista" in url
        assert "ano=2025" in url

    @pytest.mark.asyncio
    async def test_orcamento_emendas_vazio(self, mock_client):
        """Sem ano retorna DataFrame vazio."""
        mock_client.fetch.return_value = {}
        ext = OrcamentoEmendasExtractor(mock_client)
        df = await ext.extract(ano=2000)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestOrcamentoOficiosSourceUrl:
    """Testes para OrcamentoOficiosExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_orcamento_oficios_source_url(self, mock_client):
        """_source_url deve conter orcamento/oficios?ano=YYYY."""
        mock_client.fetch.return_value = [{"codigo": 1, "tipo": "Ofício"}]
        ext = OrcamentoOficiosExtractor(mock_client)
        df = await ext.extract(ano=2025)

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert "orcamento/oficios" in url
        assert "ano=2025" in url

    @pytest.mark.asyncio
    async def test_orcamento_oficios_vazio(self, mock_client):
        """Resposta vazia retorna DataFrame vazio."""
        mock_client.fetch.return_value = None
        ext = OrcamentoOficiosExtractor(mock_client)
        df = await ext.extract(ano=2050)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestVetosPresidenciaisSourceUrl:
    """Testes para VetosPresidenciaisExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_vetos_presidenciais_source_url(self, mock_client):
        """_source_url deve conter materia/vetos/{ano}."""
        mock_client.fetch.return_value = {
            "ListaVetosAnoCN": {
                "Vetos": {
                    "Veto": [{"Codigo": 1, "Assunto": "Veto X"}],
                },
            },
        }
        ext = VetosPresidenciaisExtractor(mock_client)
        df = await ext.extract(ano=2020)

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert df.columns[0] == "_source_url"
        url = df["_source_url"][0]
        assert "materia/vetos/2020" in url

    @pytest.mark.asyncio
    async def test_vetos_presidenciais_vazio(self, mock_client):
        """Resposta vazia retorna DataFrame vazio."""
        mock_client.fetch.return_value = {}
        ext = VetosPresidenciaisExtractor(mock_client)
        df = await ext.extract(ano=1900)

        assert df.is_empty()
        assert "_source_url" not in df.columns


class TestVetosDetalheSourceUrl:
    """Testes para VetosDetalheExtractor _source_url."""

    @pytest.mark.asyncio
    async def test_vetos_detalhe_source_url(self, mock_client):
        """_source_url deve conter plenario/resultado/veto/{codigo}."""
        mock_client.fetch.return_value = {
            "ResultadoVetoItemCN": {
                "Veto": {"Codigo": 1, "Assunto": "Veto X"},
            },
        }
        ext = VetosDetalheExtractor(mock_client)
        df = await ext.extract(entity_ids=[1])

        assert not df.is_empty()
        assert "_source_url" in df.columns
        assert "plenario/resultado/veto/1" in df["_source_url"][0]

    @pytest.mark.asyncio
    async def test_vetos_detalhe_vazio(self, mock_client):
        """entity_ids vazio retorna DataFrame vazio."""
        ext = VetosDetalheExtractor(mock_client)
        df = await ext.extract(entity_ids=None)

        assert df.is_empty()
        assert "_source_url" not in df.columns
