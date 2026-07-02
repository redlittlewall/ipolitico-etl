"""Testes dos extratores de composição do Senado — comportamento público."""

import json

import polars as pl
import pytest
import respx

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.composicao import (
    BlocosSenadoExtractor,
    LiderancasSenadoExtractor,
    MesaCongressoExtractor,
    MesaSenadoExtractor,
)


class TestBlocosSenadoExtractor:
    """Extrator de blocos parlamentares — /composicao/lista/blocos."""

    @pytest.fixture
    def extractor(self):
        return BlocosSenadoExtractor(SenadoClient())

    @pytest.mark.asyncio
    async def test_extract_returns_dataframe(self, extractor):
        """Dados reais retornam DataFrame com blocos e membros serializados."""
        fake_data = {
            "ListaBlocoParlamentar": {
                "Blocos": {
                    "Bloco": [
                        {
                            "CodigoBloco": "346",
                            "NomeBloco": "Bloco Parlamentar Aliança",
                            "NomeApelido": "BLALIANÇA",
                            "DataCriacao": "2023-03-20",
                            "Membros": {
                                "Membro": [
                                    {
                                        "Partido": {
                                            "CodigoPartido": "418",
                                            "SiglaPartido": "PP",
                                            "NomePartido": "Progressistas",
                                        },
                                        "DataAdesao": "2023-03-20",
                                    }
                                ]
                            },
                        },
                        {
                            "CodigoBloco": "358",
                            "NomeBloco": "Bloco Parlamentar Democracia",
                            "NomeApelido": "BLDEM",
                            "DataCriacao": "2025-02-18",
                            "Membros": {
                                "Membro": [
                                    {
                                        "Partido": {
                                            "CodigoPartido": "582",
                                            "SiglaPartido": "UNIÃO",
                                            "NomePartido": "União Brasil",
                                        },
                                        "DataAdesao": "2025-02-18",
                                    }
                                ]
                            },
                        },
                    ]
                }
            }
        }

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/composicao/lista/blocos.json"
            ).respond(status_code=200, json=fake_data)

            df = await extractor.extract()

            assert df.height == 2
            assert df["CodigoBloco"][0] == "346"
            assert df["NomeBloco"][0] == "Bloco Parlamentar Aliança"
            assert "Membros" in df.columns
            # Membros deve ser string (JSON serializado)
            membros_raw = df["Membros"][0]
            assert isinstance(membros_raw, str)
            membros_parsed = json.loads(membros_raw)
            assert membros_parsed["Membro"][0]["Partido"]["SiglaPartido"] == "PP"

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self, extractor):
        """404 retorna DataFrame vazio."""
        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/composicao/lista/blocos.json"
            ).respond(status_code=404)

            df = await extractor.extract()
            assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_sem_blocos(self, extractor):
        """Lista vazia retorna DataFrame vazio."""
        fake_data = {"ListaBlocoParlamentar": {"Blocos": {"Bloco": []}}}

        with respx.mock:
            respx.get(
                "https://legis.senado.leg.br/dadosabertos/composicao/lista/blocos.json"
            ).respond(status_code=200, json=fake_data)

            df = await extractor.extract()
            assert df.is_empty()


class TestLiderancasSenadoExtractor:
    """Extrator de lideranças — /composicao/lideranca."""

    @pytest.fixture
    def extractor(self):
        return LiderancasSenadoExtractor(SenadoClient())

    @pytest.mark.asyncio
    async def test_extract_returns_dataframe(self, extractor):
        """Array plano retorna DataFrame com lideranças."""
        fake_data = [
            {
                "codigo": 15196,
                "casa": "CN",
                "codigoParlamentar": 5012,
                "dataDesignacao": "2023-01-06",
                "descricaoTipoLideranca": "Líder do Congresso Nacional",
                "siglaTipoLideranca": "L",
                "nomeParlamentar": "Randolfe Rodrigues",
                "siglaPartidoFiliacao": "PT",
                "nomePartidoFiliacao": "Partido dos Trabalhadores",
                "codigoPartidoFiliacao": 71,
                "idTipoUnidadeLideranca": 6,
                "siglaTipoUnidadeLideranca": "G",
                "descricaoTipoUnidadeLideranca": "Liderança do Governo no Congresso Nacional",
            }
        ]

        with respx.mock:
            respx.get("https://legis.senado.leg.br/dadosabertos/composicao/lideranca.json").respond(
                status_code=200, json=fake_data
            )

            df = await extractor.extract()

            assert df.height == 1
            assert df["codigo"][0] == 15196
            assert df["nomeParlamentar"][0] == "Randolfe Rodrigues"
            assert df["casa"][0] == "CN"

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self, extractor):
        """404 retorna DataFrame vazio."""
        with respx.mock:
            respx.get("https://legis.senado.leg.br/dadosabertos/composicao/lideranca.json").respond(
                status_code=404
            )

            df = await extractor.extract()
            assert df.is_empty()


class TestMesaSenadoExtractor:
    """Extrator da mesa do Senado — /composicao/mesaSF."""

    @pytest.fixture
    def extractor(self):
        return MesaSenadoExtractor(SenadoClient())

    @pytest.mark.asyncio
    async def test_extract_returns_dataframe(self, extractor):
        """Dados reais retornam DataFrame com cargos aplainados."""
        fake_data = {
            "MesaSenado": {
                "Colegiados": {
                    "Colegiado": [
                        {
                            "CodigoColegiado": "2015",
                            "NomeColegiado": "COMISSÃO DIRETORA DO SENADO FEDERAL",
                            "SiglaColegiado": "CDIR",
                            "Cargos": {
                                "Cargo": [
                                    {
                                        "Cargo": ["PRESIDENTE"],
                                        "NomeParlamentar": "Senador Davi Alcolumbre",
                                        "Bancada": "(UNIÃO-AP)",
                                        "Http": "3830",
                                        "NumeroOrdemImpressao": "1",
                                        "Origem": "P",
                                    },
                                    {
                                        "Cargo": ["1º VICE-PRESIDENTE"],
                                        "NomeParlamentar": "Senador Eduardo Gomes",
                                        "Bancada": "(PL-TO)",
                                        "Http": "3777",
                                        "NumeroOrdemImpressao": "2",
                                        "Origem": "P",
                                    },
                                ]
                            },
                        }
                    ]
                }
            }
        }

        with respx.mock:
            respx.get("https://legis.senado.leg.br/dadosabertos/composicao/mesaSF.json").respond(
                status_code=200, json=fake_data
            )

            df = await extractor.extract()

            assert df.height == 2
            assert df["NomeParlamentar"][0] == "Senador Davi Alcolumbre"
            assert json.loads(df["Cargo"][0]) == ["PRESIDENTE"]
            assert df["CodigoColegiado"][0] == "2015"
            assert df["SiglaColegiado"][0] == "CDIR"

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self, extractor):
        """404 retorna DataFrame vazio."""
        with respx.mock:
            respx.get("https://legis.senado.leg.br/dadosabertos/composicao/mesaSF.json").respond(
                status_code=404
            )

            df = await extractor.extract()
            assert df.is_empty()


class TestMesaCongressoExtractor:
    """Extrator da mesa do Congresso — /composicao/mesaCN."""

    @pytest.fixture
    def extractor(self):
        return MesaCongressoExtractor(SenadoClient())

    @pytest.mark.asyncio
    async def test_extract_returns_dataframe(self, extractor):
        """Dados reais retornam DataFrame com cargos aplainados."""
        fake_data = {
            "MesaCongresso": {
                "Colegiados": {
                    "Colegiado": [
                        {
                            "CodigoColegiado": "1616",
                            "NomeColegiado": "Mesa Diretora do Congresso Nacional",
                            "SiglaColegiado": "Mesa",
                            "Cargos": {
                                "Cargo": [
                                    {
                                        "TipoCargo": "PRESIDENTE",
                                        "CodigoCargo": "1",
                                        "NomeParlamentar": "Senador Davi Alcolumbre",
                                        "CodigoParlamentar": "3830",
                                        "Bancada": "(UNIÃO-AP)",
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        }

        with respx.mock:
            respx.get("https://legis.senado.leg.br/dadosabertos/composicao/mesaCN.json").respond(
                status_code=200, json=fake_data
            )

            df = await extractor.extract()

            assert df.height == 1
            assert df["NomeParlamentar"][0] == "Senador Davi Alcolumbre"
            assert df["TipoCargo"][0] == "PRESIDENTE"
            assert df["CodigoColegiado"][0] == "1616"

    @pytest.mark.asyncio
    async def test_extract_404_returns_empty(self, extractor):
        """404 retorna DataFrame vazio."""
        with respx.mock:
            respx.get("https://legis.senado.leg.br/dadosabertos/composicao/mesaCN.json").respond(
                status_code=404
            )

            df = await extractor.extract()
            assert df.is_empty()


class TestBlocosSenadoTransformer:
    """Transformer de blocos — contrato Silver."""

    @pytest.fixture
    def transformer(self):
        from ipolitico.transformers.senado.institutional_transformer import (
            BlocosSenadoTransformer,
        )

        return BlocosSenadoTransformer()

    def test_transformer_apply_contract(self, transformer):
        """Aplica field_map e schema Silver corretamente."""
        df = pl.DataFrame(
            {
                "CodigoBloco": [346],
                "NomeBloco": ["Bloco Parlamentar Aliança"],
                "NomeApelido": ["BLALIANÇA"],
                "DataCriacao": ["2023-03-20"],
                "Membros": ['{"Membro": []}'],
            }
        )
        result = transformer.transform(df)
        assert result.schema == SILVER_SCHEMAS[DomainType.BLOCOS_SENADO.value]
        assert result["codigo"][0] == 346
        assert result["nome"][0] == "Bloco Parlamentar Aliança"

    def test_transformer_empty(self, transformer):
        """DataFrame vazio retorna vazio."""
        df = pl.DataFrame()
        result = transformer.transform(df)
        assert result.is_empty()


class TestLiderancasSenadoTransformer:
    """Transformer de lideranças — contrato Silver."""

    @pytest.fixture
    def transformer(self):
        from ipolitico.transformers.senado.institutional_transformer import (
            LiderancasSenadoTransformer,
        )

        return LiderancasSenadoTransformer()

    def test_transformer_apply_contract(self, transformer):
        """Aplica field_map e schema Silver corretamente."""
        df = pl.DataFrame(
            {
                "codigo": [15196],
                "casa": ["CN"],
                "codigoParlamentar": [5012],
                "nomeParlamentar": ["Randolfe Rodrigues"],
                "dataDesignacao": ["2023-01-06"],
                "siglaTipoLideranca": ["L"],
                "descricaoTipoLideranca": ["Líder do Congresso Nacional"],
                "siglaPartidoFiliacao": ["PT"],
                "nomePartidoFiliacao": ["Partido dos Trabalhadores"],
                "codigoPartidoFiliacao": [71],
                "idTipoUnidadeLideranca": [6],
                "siglaTipoUnidadeLideranca": ["G"],
                "descricaoTipoUnidadeLideranca": ["Liderança do Governo no Congresso Nacional"],
            }
        )
        result = transformer.transform(df)
        assert result.schema == SILVER_SCHEMAS[DomainType.LIDERANCAS_SENADO.value]
        assert result["codigo_parlamentar"][0] == 5012
        assert result["nome_parlamentar"][0] == "Randolfe Rodrigues"


class TestMesaSenadoTransformer:
    """Transformer da mesa do Senado — contrato Silver."""

    @pytest.fixture
    def transformer(self):
        from ipolitico.transformers.senado.institutional_transformer import (
            MesaSenadoTransformer,
        )

        return MesaSenadoTransformer()

    def test_transformer_apply_contract(self, transformer):
        """Aplica field_map e schema Silver corretamente."""
        df = pl.DataFrame(
            {
                "CodigoColegiado": ["2015"],
                "NomeColegiado": ["COMISSÃO DIRETORA DO SENADO FEDERAL"],
                "SiglaColegiado": ["CDIR"],
                "Cargo": [json.dumps(["PRESIDENTE"])],
                "NomeParlamentar": ["Senador Davi Alcolumbre"],
                "Bancada": ["(UNIÃO-AP)"],
                "Http": ["3830"],
                "NumeroOrdemImpressao": ["1"],
                "Origem": ["P"],
            }
        )
        result = transformer.transform(df)
        assert result.schema == SILVER_SCHEMAS[DomainType.MESA_SENADO.value]
        assert result["nome_parlamentar"][0] == "Senador Davi Alcolumbre"


class TestMesaCongressoTransformer:
    """Transformer da mesa do Congresso — contrato Silver."""

    @pytest.fixture
    def transformer(self):
        from ipolitico.transformers.senado.institutional_transformer import (
            MesaCongressoTransformer,
        )

        return MesaCongressoTransformer()

    def test_transformer_apply_contract(self, transformer):
        """Aplica field_map e schema Silver corretamente."""
        df = pl.DataFrame(
            {
                "CodigoColegiado": ["1616"],
                "NomeColegiado": ["Mesa Diretora do Congresso Nacional"],
                "SiglaColegiado": ["Mesa"],
                "TipoCargo": ["PRESIDENTE"],
                "CodigoCargo": ["1"],
                "NomeParlamentar": ["Senador Davi Alcolumbre"],
                "CodigoParlamentar": ["3830"],
                "Bancada": ["(UNIÃO-AP)"],
            }
        )
        result = transformer.transform(df)
        assert result.schema == SILVER_SCHEMAS[DomainType.MESA_CONGRESSO.value]
        assert result["tipo_cargo"][0] == "PRESIDENTE"
