"""Testes dos extratores de vetos presidenciais — novo envelope ListaVetosAnoCN."""

import polars as pl
import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.vetos import (
    VetosDetalheExtractor,
    VetosPresidenciaisExtractor,
)


def _make_list_veto(codigo: int, ano: int) -> dict:
    """Gera um registro de veto no formato do novo envelope ListaVetosAnoCN."""
    return {
        "Codigo": str(codigo),
        "Materia": {
            "Codigo": str(codigo * 10),
            "SiglaCasa": "CN",
            "NomeCasa": "Congresso Nacional",
            "Sigla": "VET",
            "Numero": str(codigo),
            "Ano": str(ano),
            "EmTramitacao": "Sim",
            "Ementa": f"Veto {codigo}",
            "UrlMovimentacoes": f"https://exemplo.com/mov/{codigo}",
        },
        "MateriaVetada": {
            "Codigo": str(codigo * 100),
            "SiglaCasa": "CN",
            "NomeCasa": "Congresso Nacional",
            "Sigla": "PL",
            "Numero": str(codigo),
            "Ano": str(ano - 2),
            "DescricaoObjetivoProcesso": "Revisora",
            "EmTramitacao": "Nao",
            "Ementa": f"Projeto {codigo}",
            "UrlMovimentacoes": f"https://exemplo.com/mov/{codigo}",
            "UrlRelatorias": f"https://exemplo.com/rel/{codigo}",
            "NormaGerada": {
                "NomeNorma": f"Lei {codigo}",
                "UrlNorma": f"https://exemplo.com/lei/{codigo}",
                "CodigoNorma": str(codigo),
                "SiglaTipoNorma": "LEI",
                "DescricaoTipoNorma": "Lei Numerada",
                "NumeroNorma": str(codigo),
                "AnoNorma": str(ano),
                "DataAssinatura": f"{ano}-12-30",
                "DataPublicacao": f"{ano}-12-31",
                "SiglaVeiculoPublicacao": "DOU",
                "DescricaoVeiculoPublicacao": "Diario Oficial",
            },
        },
        "Mensagem": {
            "Sigla": "MSG",
            "Numero": str(codigo),
            "Ano": str(ano),
            "UrlPlanalto": f"https://planalto.gov.br/msg/{codigo}",
        },
        "Total": "Nao",
        "Assunto": f"Assunto {codigo}",
        "DataRecebimentoCongresso": f"{ano}-01-15",
        "DataPublicacao": f"{ano}-12-31",
        "DataSobrestacaoPauta": f"{ano}-03-01",
        "SobrestandoPauta": "Nao",
        "QuantidadeDispositivos": "3",
        "UrlDispositivos": f"https://exemplo.com/disp/{codigo}",
    }


def _make_detail_veto(codigo: int, ano: int) -> dict:
    """Gera um registro de veto no formato do novo envelope ResultadoVetoItemCN."""
    base = _make_list_veto(codigo, ano)
    base["Dispositivos"] = {
        "Dispositivo": [
            {
                "Codigo": str(codigo * 10 + 1),
                "Descricao": f"Dispositivo {codigo}.1",
                "Situacao": "Mantido",
                "PossuiVotos": "Nao",
            }
        ]
    }
    return base


class TestVetosPresidenciaisExtractor:
    """Testes do VetosPresidenciaisExtractor — novo envelope ListaVetosAnoCN."""

    API_BASE = "https://legis.senado.leg.br/dadosabertos"

    @pytest.mark.asyncio
    async def test_extract_ano_returns_dataframe(self):
        """extract(ano=2024) chama o endpoint e retorna DataFrame com campos aplainados."""
        client = SenadoClient()
        extractor = VetosPresidenciaisExtractor(client)

        api_response = {
            "ListaVetosAnoCN": {
                "Metadados": {"Versao": "2026-01-01"},
                "Vetos": {
                    "Veto": [
                        _make_list_veto(codigo=17011, ano=2024),
                    ]
                },
            }
        }

        with respx.mock:
            respx.get(f"{self.API_BASE}/materia/vetos/2024.json").respond(
                status_code=200, json=api_response
            )

            df = await extractor.extract(ano=2024)

            assert df.height == 1
            # Campos flat principais
            assert "Codigo" in df.columns
            assert "Total" in df.columns
            assert "Assunto" in df.columns
            # Campos nested aplainados
            assert "Materia_Codigo" in df.columns
            assert "Materia_Sigla" in df.columns
            assert "MateriaVetada_Ementa" in df.columns
            assert "MateriaVetada_NormaGerada_NomeNorma" in df.columns
            assert "Mensagem_UrlPlanalto" in df.columns

    @pytest.mark.asyncio
    async def test_extract_multiple_years(self):
        """Múltiplos anos produzem DataFrames com dados aplainados."""
        client = SenadoClient()
        extractor = VetosPresidenciaisExtractor(client)

        with respx.mock:
            for ano in [2023, 2024]:
                respx.get(f"{self.API_BASE}/materia/vetos/{ano}.json").respond(
                    status_code=200,
                    json={
                        "ListaVetosAnoCN": {
                            "Metadados": {},
                            "Vetos": {"Veto": [_make_list_veto(codigo=ano * 10, ano=ano)]},
                        }
                    },
                )

            df_2023 = await extractor.extract(ano=2023)
            df_2024 = await extractor.extract(ano=2024)

            assert df_2023.height == 1
            assert df_2024.height == 1

    @pytest.mark.asyncio
    async def test_extract_empty_ano(self):
        """Ano sem vetos retorna DataFrame vazio."""
        client = SenadoClient()
        extractor = VetosPresidenciaisExtractor(client)

        with respx.mock:
            respx.get(f"{self.API_BASE}/materia/vetos/1990.json").respond(
                status_code=200,
                json={"ListaVetosAnoCN": {"Metadados": {}, "Vetos": {"Veto": []}}},
            )

            df = await extractor.extract(ano=1990)

            assert df.is_empty()


class TestVetosDetalheExtractor:
    """Testes do VetosDetalheExtractor — novo envelope ResultadoVetoItemCN."""

    API_BASE = "https://legis.senado.leg.br/dadosabertos"

    @pytest.mark.asyncio
    async def test_extract_entity_ids_returns_dataframe(self):
        """extract(entity_ids=[17011]) chama endpoint e retorna DataFrame aplainado."""
        client = SenadoClient()
        extractor = VetosDetalheExtractor(client)

        api_response = {
            "ResultadoVetoItemCN": {
                "Metadados": {"Versao": "2026-01-01"},
                "Veto": _make_detail_veto(codigo=17011, ano=2024),
            }
        }

        with respx.mock:
            respx.get(f"{self.API_BASE}/plenario/resultado/veto/17011.json").respond(
                status_code=200, json=api_response
            )

            df = await extractor.extract(entity_ids=[17011])

            assert df.height == 1
            assert "Codigo" in df.columns
            assert "Materia_Codigo" in df.columns
            assert "Dispositivos" in df.columns

    @pytest.mark.asyncio
    async def test_extract_multiple_entities(self):
        """Múltiplos entity_ids produzem múltiplas linhas."""
        client = SenadoClient()
        extractor = VetosDetalheExtractor(client)

        with respx.mock:
            for codigo in [17011, 17010]:
                respx.get(f"{self.API_BASE}/plenario/resultado/veto/{codigo}.json").respond(
                    status_code=200,
                    json={
                        "ResultadoVetoItemCN": {
                            "Metadados": {},
                            "Veto": _make_detail_veto(codigo=codigo, ano=2024),
                        }
                    },
                )

            df = await extractor.extract(entity_ids=[17011, 17010])

            assert df.height == 2
            assert sorted(df["Codigo"].cast(pl.Int64).to_list()) == [17010, 17011]

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
            respx.get(f"{self.API_BASE}/plenario/resultado/veto/17011.json").respond(
                status_code=200,
                json={
                    "ResultadoVetoItemCN": {
                        "Metadados": {},
                        "Veto": _make_detail_veto(codigo=17011, ano=2024),
                    }
                },
            )
            respx.get(f"{self.API_BASE}/plenario/resultado/veto/999.json").respond(status_code=404)

            df = await extractor.extract(entity_ids=[17011, 999])

            assert df.height == 1
