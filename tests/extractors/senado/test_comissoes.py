"""Testes dos extratores de comissões do Senado — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.comissoes import (
    SenadoComissoesDetalheExtractor,
    SenadoComissoesListaExtractor,
    SenadoComissoesMembrosExtractor,
    SenadoComissoesReunioesExtractor,
)


class TestSenadoComissoesListaExtractor:
    """Extrator de lista de comissões do Senado — /comissao/lista/colegiados."""

    @pytest.fixture
    def extractor(self):
        return SenadoComissoesListaExtractor(SenadoClient())

    @pytest.mark.asyncio
    async def test_extract_returns_dataframe(self, extractor):
        """Dados reais retornam DataFrame com registros."""
        fake_data = {
            "ListaColegiados": {
                "Colegiados": {
                    "Colegiado": [
                        {
                            "Codigo": "38",
                            "Sigla": "CAE",
                            "Nome": "Comissão de Assuntos Econômicos",
                            "DataInicio": "1900-01-01",
                            "Publica": "S",
                            "CodigoTipoColegiado": "21",
                            "SiglaTipoColegiado": "PERMANENTE",
                            "DescricaoTipoColegiado": "Comissão Permanente",
                            "SiglaCasa": "SF",
                        }
                    ]
                }
            }
        }

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/comissao/lista/colegiados.json"
            ).respond(status_code=200, json=fake_data)

            df = await extractor.extract()

            assert df.height == 1
            assert df["Codigo"][0] == "38"
            assert df["Sigla"][0] == "CAE"

    @pytest.mark.asyncio
    async def test_extract_empty_response(self, extractor):
        """Envelope vazio retorna DataFrame vazio."""
        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/comissao/lista/colegiados.json"
            ).respond(status_code=200, json={"ListaColegiados": {}})

            df = await extractor.extract()
            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self, extractor):
        """Falso 404 retorna DataFrame vazio."""
        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/comissao/lista/colegiados.json"
            ).respond(status_code=404)

            df = await extractor.extract()
            assert df.is_empty()


class TestSenadoComissoesDetalheExtractor:
    """Extrator de detalhes de comissão — /comissao/{codigo}."""

    @pytest.fixture
    def extractor(self):
        return SenadoComissoesDetalheExtractor(SenadoClient())

    @pytest.mark.asyncio
    async def test_extract_returns_dataframe(self, extractor):
        """Dados reais retornam DataFrame com registro único."""
        fake_data = {
            "ComissoesCongressoNacional": {
                "Colegiados": {
                    "Colegiado": [
                        {
                            "CodigoColegiado": "38",
                            "NomeColegiado": "Comissão de Assuntos Econômicos",
                            "SiglaColegiado": "CAE",
                            "DataInicio": "01/01/1900",
                            "Requerimentos": {},
                            "Cargos": {"Cargo": [{"TipoCargo": "PRESIDENTE"}]},
                            "QuantidadesMembros": {"Distribuicao": {"Senadores": "54"}},
                        }
                    ]
                }
            }
        }

        with respx.mock:
            respx.get("https://legis.senado.leg.br/dadosabertos/comissao/38.json").respond(
                status_code=200, json=fake_data
            )

            df = await extractor.extract(codigo_comissao=38)

            assert df.height == 1
            assert df["CodigoColegiado"][0] == "38"
            assert df["NomeColegiado"][0] == "Comissão de Assuntos Econômicos"

    @pytest.mark.asyncio
    async def test_extract_sem_codigo_retorna_vazio(self, extractor):
        """Sem código de comissão, retorna DataFrame vazio."""
        df = await extractor.extract()
        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self, extractor):
        """Comissão inexistente retorna DataFrame vazio."""
        with respx.mock:
            respx.get("https://legis.senado.leg.br/dadosabertos/comissao/999.json").respond(
                status_code=404
            )

            df = await extractor.extract(codigo_comissao=999)
            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_heterogeneous_schema_unifies(self, extractor):
        """
        Comissões com campos diferentes (ex: uma com ``Cargos``, outra com
        ``Composicao``) são unificadas em um único DataFrame. O concat
        por-comissão falhava com SchemaError; o DataFrame único preenche com
        null os campos ausentes.
        """
        comissao_a = {
            "ComissoesCongressoNacional": {
                "Colegiados": {
                    "Colegiado": [
                        {
                            "CodigoColegiado": "38",
                            "NomeColegiado": "CAE",
                            "Cargos": {"Cargo": [{"TipoCargo": "PRESIDENTE"}]},
                        }
                    ]
                }
            }
        }
        comissao_b = {
            "ComissoesCongressoNacional": {
                "Colegiados": {
                    "Colegiado": [
                        {
                            "CodigoColegiado": "1",
                            "NomeColegiado": "CCJ",
                            "Composicao": [{"Cargo": "Membro"}],
                        }
                    ]
                }
            }
        }

        with respx.mock:
            respx.get("https://legis.senado.leg.br/dadosabertos/comissao/38.json").respond(
                status_code=200, json=comissao_a
            )
            respx.get("https://legis.senado.leg.br/dadosabertos/comissao/1.json").respond(
                status_code=200, json=comissao_b
            )

            df = await extractor.extract(entity_ids=[38, 1])

            assert df.height == 2
            assert "Composicao" in df.columns
            assert df["Composicao"].to_list()[0] is None
            assert df["Cargos"].to_list()[1] is None


class TestSenadoComissoesReunioesExtractor:
    """Extrator de agenda de reuniões — /comissao/agenda/{inicio}/{fim}."""

    @pytest.fixture
    def extractor(self):
        return SenadoComissoesReunioesExtractor(SenadoClient())

    @pytest.mark.asyncio
    async def test_extract_returns_dataframe(self, extractor):
        """Dados reais retornam DataFrame com registros."""
        fake_data = {
            "AgendaReuniao": {
                "reunioes": {
                    "reuniao": [
                        {
                            "codigo": "13683",
                            "versao": "2026-03-19T02:03:51.827",
                            "descricao": "33ª, Extraordinária",
                            "titulo": "33ª Reunião Extraordinária",
                            "colegiadoCriador": {
                                "codigo": "834",
                                "sigla": "CDH",
                                "nome": "Comissão de Direitos Humanos",
                            },
                            "dataInicio": "2025-06-30T09:30:00.000",
                            "local": "Anexo II, Plenário nº 2",
                            "situacao": "Realizada",
                            "status": "Realizada",
                            "secreta": "false",
                            "tipoPresenca": "Presencial",
                            "realizada": "true",
                            "confirmada": "false",
                            "codigoSituacao": "6",
                            "linkECidadania": "https://example.com",
                            "urlUltimaPautaSimplesPublicada": "https://example.com/pauta",
                            "urlUltimaPautaCheiaPublicada": "https://example.com/cheia",
                            "urlUltimoResultadoPublicado": "https://example.com/resultado",
                        }
                    ]
                }
            }
        }

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/comissao/agenda/20250601/20250630.json"
            ).respond(status_code=200, json=fake_data)

            df = await extractor.extract(
                start_date="2025-06-01",
                end_date="2025-06-30",
            )

            assert df.height == 1
            assert df["codigo"][0] == "13683"
            assert df["CodigoColegiado"][0] == "834"

    @pytest.mark.asyncio
    async def test_extract_empty_response(self, extractor):
        """Período sem reuniões retorna DataFrame vazio."""
        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/comissao/agenda/20250101/20250131.json"
            ).respond(status_code=200, json={"AgendaReuniao": {"reunioes": {}}})

            df = await extractor.extract(
                start_date="2025-01-01",
                end_date="2025-01-31",
            )
            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self, extractor):
        """404 retorna DataFrame vazio."""
        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/comissao/agenda/20990101/20990131.json"
            ).respond(status_code=404)

            df = await extractor.extract(
                start_date="2099-01-01",
                end_date="2099-01-31",
            )
            assert df.is_empty()


class TestSenadoComissoesMembrosExtractor:
    """Extrator de membros de comissão — /composicao/comissao/{codigo}."""

    @pytest.fixture
    def extractor(self):
        return SenadoComissoesMembrosExtractor(SenadoClient())

    @pytest.mark.asyncio
    async def test_extract_returns_dataframe(self, extractor):
        """Dados reais retornam DataFrame com registros + dados da comissão."""
        fake_data = {
            "ComposicaoAtivaComissaoSf": {
                "ComposicaoComissao": {
                    "IdentificacaoComissao": [
                        {
                            "CodigoComissao": "38",
                            "SiglaComissao": "CAE",
                            "NomeComissao": "Comissão de Assuntos Econômicos",
                        }
                    ],
                    "Membros": {
                        "Membro": [
                            {
                                "NomeMembro": "Alan Rick",
                                "CodigoMembro": "5672",
                                "TipoVaga": "Titular",
                                "IndicadorVagaAtiva": "Sim",
                                "DataInicioMembroVaga": "2025-11-26",
                            }
                        ]
                    },
                }
            }
        }

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/composicao/comissao/38.json",
                params={"ativas": "S"},
            ).respond(status_code=200, json=fake_data)

            df = await extractor.extract(codigo_comissao=38)

            assert df.height == 1
            assert df["NomeMembro"][0] == "Alan Rick"
            assert df["CodigoComissao"][0] == "38"
            assert df["SiglaComissao"][0] == "CAE"

    @pytest.mark.asyncio
    async def test_extract_sem_codigo_retorna_vazio(self, extractor):
        """Sem código, retorna DataFrame vazio."""
        df = await extractor.extract()
        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_empty_response(self, extractor):
        """Comissão sem membros retorna DataFrame vazio."""
        fake_data = {
            "ComposicaoAtivaComissaoSf": {
                "ComposicaoComissao": {
                    "IdentificacaoComissao": [{"CodigoComissao": "38"}],
                    "Membros": {"Membro": []},
                }
            }
        }

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/composicao/comissao/38.json",
                params={"ativas": "S"},
            ).respond(status_code=200, json=fake_data)

            df = await extractor.extract(codigo_comissao=38)
            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self, extractor):
        """Comissão inexistente retorna DataFrame vazio."""
        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/composicao/comissao/999.json",
                params={"ativas": "S"},
            ).respond(status_code=404)

            df = await extractor.extract(codigo_comissao=999)
            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_membros_heterogeneous_schema_unifies(self, extractor):
        """
        Membros de comissões diferentes com campos distintos são unificados
        em um único DataFrame (ex: um com ``TipoVaga``, outro com
        ``DataFimMembroVaga``). O concat por-comissão falhava com SchemaError.
        """
        def _composicao(codigo: str, membros: list[dict]) -> dict:
            return {
                "ComposicaoAtivaComissaoSf": {
                    "ComposicaoComissao": {
                        "IdentificacaoComissao": [
                            {
                                "CodigoComissao": codigo,
                                "SiglaComissao": f"S{codigo}",
                                "NomeComissao": f"Comissão {codigo}",
                            }
                        ],
                        "Membros": {"Membro": membros},
                    }
                }
            }

        membros_a = [{"NomeMembro": "Alan Rick", "CodigoMembro": "5672", "TipoVaga": "Titular"}]
        membros_b = [{"NomeMembro": "Marcio Bittar", "CodigoMembro": "1000", "DataFimMembroVaga": "2027-01-01"}]

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/composicao/comissao/38.json",
                params={"ativas": "S"},
            ).respond(status_code=200, json=_composicao("38", membros_a))
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/composicao/comissao/1.json",
                params={"ativas": "S"},
            ).respond(status_code=200, json=_composicao("1", membros_b))

            df = await extractor.extract(entity_ids=[38, 1])

            assert df.height == 2
            assert "DataFimMembroVaga" in df.columns
            assert df["DataFimMembroVaga"].to_list()[0] is None
            assert df["TipoVaga"].to_list()[1] is None
