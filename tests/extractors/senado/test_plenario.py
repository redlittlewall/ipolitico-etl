"""Testes dos extratores de plenário do Senado — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.plenario import (
    PlenarioAgendaExtractor,
    PlenarioResultadosExtractor,
    PlenarioSessoesExtractor,
)


class TestPlenarioAgendaExtractor:
    """Extrator da agenda do plenário — /plenario/agenda/dia/{data}."""

    @pytest.fixture
    def extractor(self):
        return PlenarioAgendaExtractor(SenadoClient())

    @pytest.mark.asyncio
    async def test_extract_returns_dataframe(self, extractor):
        """Dados reais retornam DataFrame com registros e structs serializadas."""
        fake_data = {
            "AgendaPlenario": {
                "Sessoes": {
                    "Sessao": [
                        {
                            "CodigoSessao": "564648",
                            "Data": "2026-06-10",
                            "DiaSemana": "quarta-feira",
                            "Hora": "14:00",
                            "NumeroSessao": "77ª SESSÃO ",
                            "TipoSessao": "SESSÃO DELIBERATIVA ORDINÁRIA ",
                            "LocalSessao": "Plenário do Senado Federal",
                            "Casa": "SF",
                            "SessaoLegislativa": "4",
                            "Legislatura": "57",
                            "CodigoSituacaoSessao": "40",
                            "SituacaoSessao": "Encerrada",
                            "Realizada": {"Status": "Sim"},
                            "PautaConfirmada": "Sim",
                            "TipoPresenca": "P",
                            "DescricaoTipoPresenca": "Presencial",
                        }
                    ]
                }
            }
        }

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/plenario/agenda/dia/20260610.json"
            ).respond(status_code=200, json=fake_data)

            df = await extractor.extract(data="2026-06-10")

            assert df.height == 1
            assert df["CodigoSessao"][0] == "564648"
            assert "Realizada" in df.columns

    @pytest.mark.asyncio
    async def test_extract_sem_data_retorna_vazio(self, extractor):
        """Sem parâmetro data, retorna DataFrame vazio."""
        df = await extractor.extract()
        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self, extractor):
        """404 retorna DataFrame vazio."""
        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/plenario/agenda/dia/20990101.json"
            ).respond(status_code=404)

            df = await extractor.extract(data="2099-01-01")
            assert df.is_empty()


class TestPlenarioResultadosExtractor:
    """Extrator de resultados de votações — /plenario/resultado/{data}."""

    @pytest.fixture
    def extractor(self):
        return PlenarioResultadosExtractor(SenadoClient())

    @pytest.mark.asyncio
    async def test_extract_returns_dataframe(self, extractor):
        """Dados reais retornam DataFrame com itens e metadados da sessão."""
        fake_data = {
            "ResultadoPlenario": {
                "Sessoes": {
                    "Sessao": [
                        {
                            "codigoSessao": "564648",
                            "numeroSessao": "77",
                            "dataSessao": "10/06/2026",
                            "horaSessao": "14:00",
                            "diaSessao": "quarta-feira",
                            "tipoSessao": "DOR",
                            "descricaoTipoSessao": "Sessão Deliberativa Ordinária",
                            "siglaCasa": "SF",
                            "Itens": {
                                "Item": [
                                    {
                                        "codigoItem": "571562",
                                        "codigoMateria": "173720",
                                        "idIdentificacao": "9036481",
                                        "identificacao": "OFÍCIO Nº 4, DE 2026",
                                        "ementaPapeleta": "submete à apreciação...",
                                        "siglaCasaMateria": "CN",
                                        "siglaMateria": "OFS",
                                        "numeroMateria": "00004",
                                        "anoMateria": "2026",
                                        "DescricaoIdentificacaoMateria": "Ofício n° 4, de 2026",
                                        "textoResultado": "Resultado: Aprovada",
                                        "indicadorDeliberacao": "S",
                                        "descricaoDeliberacao": "Apreciado",
                                        "sequencialItem": "1",
                                        "tipoPauta": "O",
                                        "descricaoTipoPauta": "Pauta",
                                        "indicadorRevisado": "N",
                                        "codigoTipoApreciacao": "13",
                                        "descricaoTipoApreciacao": "Votação, em turno único",
                                        "autorMateria": "Superior Tribunal de Justiça",
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        }

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/plenario/resultado/20260610.json"
            ).respond(status_code=200, json=fake_data)

            df = await extractor.extract(data="2026-06-10")

            assert df.height == 1
            assert df["codigoItem"][0] == "571562"
            assert df["dataSessao"][0] == "10/06/2026"
            assert df["siglaCasa"][0] == "SF"

    @pytest.mark.asyncio
    async def test_extract_sem_data_retorna_vazio(self, extractor):
        """Sem parâmetro data, retorna DataFrame vazio."""
        df = await extractor.extract()
        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self, extractor):
        """404 retorna DataFrame vazio."""
        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/plenario/resultado/20990101.json"
            ).respond(status_code=404)

            df = await extractor.extract(data="2099-01-01")
            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_sessao_sem_itens(self, extractor):
        """Sessão sem Itens retorna DataFrame vazio."""
        fake_data = {
            "ResultadoPlenario": {
                "Sessoes": {
                    "Sessao": [
                        {
                            "codigoSessao": "564648",
                            "dataSessao": "10/06/2026",
                            "siglaCasa": "SF",
                        }
                    ]
                }
            }
        }

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/plenario/resultado/20260610.json"
            ).respond(status_code=200, json=fake_data)

            df = await extractor.extract(data="2026-06-10")
            assert df.is_empty()


class TestPlenarioSessoesExtractor:
    """Extrator de sessões legislativas — /plenario/legislatura/{data}."""

    @pytest.fixture
    def extractor(self):
        return PlenarioSessoesExtractor(SenadoClient())

    @pytest.mark.asyncio
    async def test_extract_returns_dataframe(self, extractor):
        """Dados reais retornam DataFrame com sessões e metadados da legislatura."""
        fake_data = {
            "ListaLegislatura": {
                "Legislaturas": {
                    "Legislatura": [
                        {
                            "NumeroLegislatura": "57",
                            "DataInicio": "2023-02-01",
                            "DataFim": "2027-01-31",
                            "DataEleicao": "2022-10-02",
                            "SessoesLegislativas": {
                                "SessaoLegislativa": [
                                    {
                                        "NumeroSessaoLegislativa": "1",
                                        "TipoSessaoLegislativa": "Ordinária",
                                        "DataInicio": "2023-02-02",
                                        "DataFim": "2023-12-22",
                                    },
                                    {
                                        "NumeroSessaoLegislativa": "4",
                                        "TipoSessaoLegislativa": "Ordinária",
                                        "DataInicio": "2026-02-02",
                                        "DataFim": "2026-12-22",
                                    },
                                ]
                            },
                        }
                    ]
                }
            }
        }

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/plenario/legislatura/20260610.json"
            ).respond(status_code=200, json=fake_data)

            df = await extractor.extract(data="2026-06-10")

            assert df.height == 2
            assert df["NumeroSessaoLegislativa"][0] == "1"
            assert df["NumeroLegislatura"][0] == "57"
            assert df["DataEleicao"][0] == "2022-10-02"

    @pytest.mark.asyncio
    async def test_extract_sem_data_retorna_vazio(self, extractor):
        """Sem parâmetro data, retorna DataFrame vazio."""
        df = await extractor.extract()
        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self, extractor):
        """404 retorna DataFrame vazio."""
        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/plenario/legislatura/20990101.json"
            ).respond(status_code=404)

            df = await extractor.extract(data="2099-01-01")
            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_sem_sessoes(self, extractor):
        """Legislatura sem SessoesLegislativas retorna DataFrame vazio."""
        fake_data = {
            "ListaLegislatura": {
                "Legislaturas": {
                    "Legislatura": [
                        {
                            "NumeroLegislatura": "57",
                            "SessoesLegislativas": {},
                        }
                    ]
                }
            }
        }

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/plenario/legislatura/20260610.json"
            ).respond(status_code=200, json=fake_data)

            df = await extractor.extract(data="2026-06-10")
            assert df.is_empty()
