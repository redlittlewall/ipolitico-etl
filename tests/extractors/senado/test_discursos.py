"""Testes dos extratores de discursos e notas taquigráficas — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.discursos import (
    DiscursosPlenarioExtractor,
    DiscursosSenadorExtractor,
    DiscursosTextoExtractor,
    NotasTaquigrafiaReuniaoExtractor,
    NotasTaquigrafiaSessaoExtractor,
)

# ── DiscursosPlenarioExtractor ────────────────────────────────────────────────


class TestDiscursosPlenarioExtractor:
    """Testes do DiscursosPlenarioExtractor — endpoint flat sem XML-heritage."""

    def _fake_discursos_plenario(self):
        return [
            {
                "Codigo": 12345,
                "Data": "2025-03-15",
                "TipoDiscurso": "Pela ordem",
                "Fase": "Ordem do Dia",
                "Resumo": "Discussão sobre o PL 123/2025",
                "NomeParlamentar": "Sen. João Silva",
                "SiglaPartido": "PT",
                "UF": "SP",
            }
        ]

    @pytest.mark.asyncio
    async def test_extract_happy_path(self):
        """
        extract(start_date, end_date) chama o endpoint correto com as datas
        no path e retorna um DataFrame com os registros.
        """
        client = SenadoClient()
        extractor = DiscursosPlenarioExtractor(client)

        api_response = self._fake_discursos_plenario()

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/plenario/lista/discursos/20250301/20250331.json"
            ).respond(status_code=200, json=api_response)

            df = await extractor.extract(start_date="2025-03-01", end_date="2025-03-31")

            assert df.height == 1
            assert "Codigo" in df.columns
            assert df["Codigo"][0] == 12345

    @pytest.mark.asyncio
    async def test_extract_empty_response(self):
        """Lista vazia retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = DiscursosPlenarioExtractor(client)

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/plenario/lista/discursos/20250101/20250131.json"
            ).respond(status_code=200, json=[])

            df = await extractor.extract(start_date="2025-01-01", end_date="2025-01-31")

            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_not_list_returns_empty(self):
        """Resposta que não é lista (ex: dict de erro) retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = DiscursosPlenarioExtractor(client)

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/plenario/lista/discursos/20250101/20250131.json"
            ).respond(status_code=200, json={"error": "not an array"})

            df = await extractor.extract(start_date="2025-01-01", end_date="2025-01-31")

            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self):
        """Falso 404: período sem discursos retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = DiscursosPlenarioExtractor(client)

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/plenario/lista/discursos/20990101/20990131.json"
            ).respond(status_code=404)

            df = await extractor.extract(start_date="2099-01-01", end_date="2099-01-31")

            assert df.is_empty()


# ── DiscursosSenadorExtractor ─────────────────────────────────────────────────


class TestDiscursosSenadorExtractor:
    """Testes do DiscursosSenadorExtractor — XML-heritage com objeto-único vs lista."""

    FAKE_DISCURSO = {
        "Codigo": "54321",
        "Data": "2025-03-15",
        "Hora": "14:30",
        "TipoDiscurso": "Grande Expediente",
        "Resumo": "Pronunciamento sobre educação",
        "Texto": "Senhor presidente, Sras. e Srs. Senadores...",
    }

    def _build_envelope(self, pronunciamentos):
        """Monta envelope XML-heritage completo."""
        return {
            "Parlamentar": {
                "IdentificacaoParlamentar": {
                    "CodigoParlamentar": "123",
                    "NomeParlamentar": "Sen. João Silva",
                    "SiglaPartido": "PT",
                    "UF": "SP",
                },
                "Pronunciamentos": {
                    "Pronunciamento": pronunciamentos,
                },
            }
        }

    @pytest.mark.asyncio
    async def test_extract_single_speech(self):
        """
        Quando há 1 discurso, Pronunciamento é objeto — _ensure_list normaliza.
        """
        client = SenadoClient()
        extractor = DiscursosSenadorExtractor(client)

        api_response = self._build_envelope(self.FAKE_DISCURSO)

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/senador/123/discursos.json",
                params={"dataInicio": "2025-03-01", "dataFim": "2025-03-31"},
            ).respond(status_code=200, json=api_response)

            df = await extractor.extract(codigo=123, dataInicio="2025-03-01", dataFim="2025-03-31")

            assert df.height == 1
            assert df["Codigo"][0] == "54321"
            assert "Pronunciamentos" not in df.columns  # envelope achatado

    @pytest.mark.asyncio
    async def test_extract_multiple_speeches(self):
        """
        Quando há 2+ discursos, Pronunciamento é lista — retorna todos.
        """
        client = SenadoClient()
        extractor = DiscursosSenadorExtractor(client)

        speeches = [self.FAKE_DISCURSO, {**self.FAKE_DISCURSO, "Codigo": "54322"}]
        api_response = self._build_envelope(speeches)

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/senador/123/discursos.json",
                params={"dataInicio": "2025-03-01", "dataFim": "2025-03-31"},
            ).respond(status_code=200, json=api_response)

            df = await extractor.extract(codigo=123, dataInicio="2025-03-01", dataFim="2025-03-31")

            assert df.height == 2
            assert df["Codigo"].to_list() == ["54321", "54322"]

    @pytest.mark.asyncio
    async def test_extract_no_parametros(self):
        """
        extract() sem parâmetros retorna DataFrame vazio (sem código).
        """
        client = SenadoClient()
        extractor = DiscursosSenadorExtractor(client)

        df = await extractor.extract()

        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self):
        """404 retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = DiscursosSenadorExtractor(client)

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/senador/999/discursos.json"
            ).respond(status_code=404)

            df = await extractor.extract(codigo=999)

            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_envelope_sem_pronunciamentos(self):
        """Envelope sem Pronunciamentos retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = DiscursosSenadorExtractor(client)

        api_response = {"Parlamentar": {}}

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/senador/123/discursos.json",
                params={"dataInicio": "2025-03-01", "dataFim": "2025-03-31"},
            ).respond(status_code=200, json=api_response)

            df = await extractor.extract(codigo=123, dataInicio="2025-03-01", dataFim="2025-03-31")

            assert df.is_empty()


# ── DiscursosTextoExtractor ───────────────────────────────────────────────────


class TestDiscursosTextoExtractor:
    """Testes do DiscursosTextoExtractor — flat per speech code."""

    @pytest.mark.asyncio
    async def test_extract_single(self):
        """
        extract(entity_ids=[codigo]) chama o endpoint e retorna dict.
        """
        client = SenadoClient()
        extractor = DiscursosTextoExtractor(client)

        api_response = {
            "Codigo": 12345,
            "Texto": "Senhor presidente, Sras. e Srs. Senadores...",
        }

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/discurso/texto-integral/12345.json"
            ).respond(status_code=200, json=api_response)

            df = await extractor.extract(entity_ids=[12345])

            assert df.height == 1
            assert "Texto" in df.columns

    @pytest.mark.asyncio
    async def test_extract_empty_entity_ids(self):
        """Lista vazia de códigos retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = DiscursosTextoExtractor(client)

        df = await extractor.extract(entity_ids=[])

        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self):
        """404 retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = DiscursosTextoExtractor(client)

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/discurso/texto-integral/99999.json"
            ).respond(status_code=404)

            df = await extractor.extract(entity_ids=[99999])

            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_heterogeneous_schema_unifies(self):
        """
        Discursos com campos diferentes (ex: um com ``Fase``, outro com
        ``Publicacao`` aninhada) são unificados em um único DataFrame.
        O concat por-discurso falhava com SchemaError.
        """
        client = SenadoClient()
        extractor = DiscursosTextoExtractor(client)

        discurso_a = {"Codigo": 1, "Texto": "Discurso A", "Fase": "Ordem do Dia"}
        discurso_b = {"Codigo": 2, "Texto": "Discurso B", "Publicacao": {"data": "2025-01-01"}}

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/discurso/texto-integral/1.json"
            ).respond(status_code=200, json=discurso_a)
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/discurso/texto-integral/2.json"
            ).respond(status_code=200, json=discurso_b)

            df = await extractor.extract(entity_ids=[1, 2])

            assert df.height == 2
            assert "Publicacao" in df.columns
            assert df["Publicacao"].to_list()[0] is None
            assert df["Fase"].to_list()[1] is None


# ── NotasTaquigrafiaSessaoExtractor ───────────────────────────────────────────


class TestNotasTaquigrafiaSessaoExtractor:
    """Testes do NotasTaquigrafiaSessaoExtractor — flat per session ID."""

    @pytest.mark.asyncio
    async def test_extract_single(self):
        """entity_ids=[idSessao] retorna dict com texto."""
        client = SenadoClient()
        extractor = NotasTaquigrafiaSessaoExtractor(client)

        api_response = {"IdSessao": 12345, "Texto": "Notas taquigráficas da sessão..."}

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/taquigrafia/notas/sessao/12345.json"
            ).respond(status_code=200, json=api_response)

            df = await extractor.extract(entity_ids=[12345])

            assert df.height == 1
            assert "Texto" in df.columns

    @pytest.mark.asyncio
    async def test_extract_empty_entity_ids(self):
        """Lista vazia retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = NotasTaquigrafiaSessaoExtractor(client)

        df = await extractor.extract(entity_ids=[])

        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self):
        """404 retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = NotasTaquigrafiaSessaoExtractor(client)

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/taquigrafia/notas/sessao/99999.json"
            ).respond(status_code=404)

            df = await extractor.extract(entity_ids=[99999])

            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_heterogeneous_schema_unifies(self):
        """
        Sessões com campos diferentes são unificadas em um único DataFrame.
        O concat por-sessão falhava com SchemaError.
        """
        client = SenadoClient()
        extractor = NotasTaquigrafiaSessaoExtractor(client)

        sessao_a = {"IdSessao": 1, "Texto": "Notas A", "OrdemDia": {"item": "1"}}
        sessao_b = {"IdSessao": 2, "Texto": "Notas B", "Local": "Plenário"}

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/taquigrafia/notas/sessao/1.json"
            ).respond(status_code=200, json=sessao_a)
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/taquigrafia/notas/sessao/2.json"
            ).respond(status_code=200, json=sessao_b)

            df = await extractor.extract(entity_ids=[1, 2])

            assert df.height == 2
            assert "Local" in df.columns
            assert df["Local"].to_list()[0] is None
            assert df["OrdemDia"].to_list()[1] is None


# ── NotasTaquigrafiaReuniaoExtractor ──────────────────────────────────────────


class TestNotasTaquigrafiaReuniaoExtractor:
    """Testes do NotasTaquigrafiaReuniaoExtractor — flat per meeting ID."""

    @pytest.mark.asyncio
    async def test_extract_single(self):
        """entity_ids=[idReuniao] retorna dict com texto."""
        client = SenadoClient()
        extractor = NotasTaquigrafiaReuniaoExtractor(client)

        api_response = {"IdReuniao": 67890, "Texto": "Notas taquigráficas da reunião..."}

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/taquigrafia/notas/reuniao/67890.json"
            ).respond(status_code=200, json=api_response)

            df = await extractor.extract(entity_ids=[67890])

            assert df.height == 1
            assert "Texto" in df.columns

    @pytest.mark.asyncio
    async def test_extract_empty_entity_ids(self):
        """Lista vazia retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = NotasTaquigrafiaReuniaoExtractor(client)

        df = await extractor.extract(entity_ids=[])

        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self):
        """404 retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = NotasTaquigrafiaReuniaoExtractor(client)

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/taquigrafia/notas/reuniao/99999.json"
            ).respond(status_code=404)

            df = await extractor.extract(entity_ids=[99999])

            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_heterogeneous_schema_unifies(self):
        """
        Reuniões com campos diferentes são unificadas em um único DataFrame.
        O concat por-reunião falhava com SchemaError.
        """
        client = SenadoClient()
        extractor = NotasTaquigrafiaReuniaoExtractor(client)

        reuniao_a = {"IdReuniao": 1, "Texto": "Notas A", "Comissao": {"sigla": "CAE"}}
        reuniao_b = {"IdReuniao": 2, "Texto": "Notas B", "Situacao": "Realizada"}

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/taquigrafia/notas/reuniao/1.json"
            ).respond(status_code=200, json=reuniao_a)
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/taquigrafia/notas/reuniao/2.json"
            ).respond(status_code=200, json=reuniao_b)

            df = await extractor.extract(entity_ids=[1, 2])

            assert df.height == 2
            assert "Situacao" in df.columns
            assert df["Situacao"].to_list()[0] is None
            assert df["Comissao"].to_list()[1] is None
