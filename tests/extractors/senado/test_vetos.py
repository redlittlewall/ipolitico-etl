"""Testes dos extratores de vetos presidenciais — comportamento público."""

import polars as pl
import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.vetos import (
    VetosDetalheExtractor,
    VetosPresidenciaisExtractor,
)


class TestVetosPresidenciaisExtractor:
    """Testes do VetosPresidenciaisExtractor — GET /materia/vetos/{ano}."""

    API_BASE = "https://legis.senado.leg.br/dadosabertos"

    @pytest.mark.asyncio
    async def test_extract_ano_returns_dataframe(self):
        """extract(ano=2020) chama o endpoint correto e retorna DataFrame."""
        client = SenadoClient()
        extractor = VetosPresidenciaisExtractor(client)

        api_response = {
            "MateriaVetos": {
                "Vetos": {
                    "Veto": [
                        {
                            "Codigo": 12345,
                            "Ano": 2020,
                            "Numero": "1",
                            "Tipo": "Total",
                            "CasaOrigem": "CN",
                            "SiglaProposicao": "PL 100/2020",
                            "Ementa": "Teste de ementa",
                            "Autor": "Executivo",
                        }
                    ]
                }
            }
        }

        with respx.mock:
            respx.get(f"{self.API_BASE}/materia/vetos/2020.json").respond(
                status_code=200, json=api_response
            )

            df = await extractor.extract(ano=2020)

            assert df.height == 1
            assert "Codigo" in df.columns
            assert "Ano" in df.columns

    @pytest.mark.asyncio
    async def test_extract_multiple_years(self):
        """Múltiplos anos produzem DataFrames separados."""
        client = SenadoClient()
        extractor = VetosPresidenciaisExtractor(client)

        with respx.mock:
            for ano in [2019, 2020]:
                respx.get(f"{self.API_BASE}/materia/vetos/{ano}.json").respond(
                    status_code=200,
                    json={
                        "MateriaVetos": {
                            "Vetos": {
                                "Veto": [
                                    {
                                        "Codigo": ano * 10,
                                        "Ano": ano,
                                        "Numero": str(ano),
                                        "Tipo": "Parcial",
                                        "CasaOrigem": "CN",
                                        "SiglaProposicao": f"PL {ano}/2020",
                                        "Ementa": f"Ementa {ano}",
                                        "Autor": "Executivo",
                                    }
                                ]
                            }
                        }
                    },
                )

            df_2019 = await extractor.extract(ano=2019)
            df_2020 = await extractor.extract(ano=2020)

            assert df_2019.height == 1
            assert df_2020.height == 1
            assert df_2019["Codigo"][0] == 20190
            assert df_2020["Codigo"][0] == 20200

    @pytest.mark.asyncio
    async def test_extract_empty_ano(self):
        """Ano sem vetos retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = VetosPresidenciaisExtractor(client)

        with respx.mock:
            respx.get(f"{self.API_BASE}/materia/vetos/1990.json").respond(
                status_code=200,
                json={"MateriaVetos": {"Vetos": {"Veto": []}}},
            )

            df = await extractor.extract(ano=1990)

            assert df.is_empty()


class TestVetosDetalheExtractor:
    """Testes do VetosDetalheExtractor — GET /plenario/resultado/veto/{codigo}."""

    API_BASE = "https://legis.senado.leg.br/dadosabertos"

    @pytest.mark.asyncio
    async def test_extract_entity_ids_returns_dataframe(self):
        """extract(entity_ids=[1]) chama o endpoint correto e retorna DataFrame."""
        client = SenadoClient()
        extractor = VetosDetalheExtractor(client)

        api_response = {
            "PlenarioVeto": {
                "Veto": {
                    "Codigo": 1,
                    "DataVotacao": "2020-06-15",
                    "Resultado": "Mantido",
                    "DescricaoResultado": "Veto mantido pelo Congresso",
                    "TotalParlamentares": 513,
                    "TotalSim": 350,
                    "TotalNao": 120,
                    "TotalAbstencao": 43,
                }
            }
        }

        with respx.mock:
            respx.get(f"{self.API_BASE}/plenario/resultado/veto/1.json").respond(
                status_code=200, json=api_response
            )

            df = await extractor.extract(entity_ids=[1])

            assert df.height == 1
            assert "Codigo" in df.columns
            assert "Resultado" in df.columns

    @pytest.mark.asyncio
    async def test_extract_multiple_entities(self):
        """Múltiplos entity_ids produzem múltiplas linhas no DataFrame."""
        client = SenadoClient()
        extractor = VetosDetalheExtractor(client)

        with respx.mock:
            for codigo in [1, 2]:
                respx.get(f"{self.API_BASE}/plenario/resultado/veto/{codigo}.json").respond(
                    status_code=200,
                    json={
                        "PlenarioVeto": {
                            "Veto": {
                                "Codigo": codigo,
                                "DataVotacao": "2020-06-15",
                                "Resultado": "Mantido" if codigo == 1 else "Derrubado",
                                "DescricaoResultado": f"Resultado {codigo}",
                                "TotalParlamentares": 513,
                                "TotalSim": 350,
                                "TotalNao": 120,
                                "TotalAbstencao": 43,
                            }
                        }
                    },
                )

            df = await extractor.extract(entity_ids=[1, 2])

            assert df.height == 2
            assert sorted(df["Codigo"].cast(pl.Int64).to_list()) == [1, 2]

    @pytest.mark.asyncio
    async def test_extract_empty_ids(self):
        """entity_ids vazio retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = VetosDetalheExtractor(client)

        df = await extractor.extract(entity_ids=[])

        assert df.is_empty()

    @pytest.mark.asyncio
    async def test_extract_404_skipped(self):
        """Veto inexistente (404) é ignorado sem quebrar o batch."""
        client = SenadoClient()
        extractor = VetosDetalheExtractor(client)

        with respx.mock:
            respx.get(f"{self.API_BASE}/plenario/resultado/veto/1.json").respond(
                status_code=200,
                json={
                    "PlenarioVeto": {
                        "Veto": {
                            "Codigo": 1,
                            "DataVotacao": "2020-06-15",
                            "Resultado": "Mantido",
                            "DescricaoResultado": "Veto mantido",
                            "TotalParlamentares": 513,
                            "TotalSim": 350,
                            "TotalNao": 120,
                            "TotalAbstencao": 43,
                        }
                    }
                },
            )
            respx.get(f"{self.API_BASE}/plenario/resultado/veto/999.json").respond(status_code=404)

            df = await extractor.extract(entity_ids=[1, 999])

            assert df.height == 1
