"""Testes dos extratores de orçamento do Senado — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.orcamento import (
    OrcamentoEmendasExtractor,
    OrcamentoOficiosExtractor,
)

# ── ORCAMENTO_EMENDAS ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_emendas_extract_ano_returns_dataframe():
    """
    OrcamentoEmendasExtractor.extract(ano=2025) chama /orcamento/lista
    com ?ano=2025, aplaina o envelope XML-heritage e retorna DataFrame.
    """
    client = SenadoClient()
    extractor = OrcamentoEmendasExtractor(client)

    fake_response = {
        "ListaLoteEmendas": {
            "Metadados": {"Versao": "30/06/2026"},
            "LotesEmendasOrcamento": {
                "LoteEmendasOrcamento": [
                    {
                        "NomeAutorOrcamento": "Abilio Brunini",
                        "IndicadorAtivo": "Não",
                        "EmailAutorOrcamento": "dep.abiliobrunini@camara.leg.br",
                        "CodigoAutorOrcamento": "4290",
                        "DataOperacao": "2023-11-29",
                        "QuantidadeEmendas": "10",
                        "AnoExecucao": "2024",
                        "NumeroMateria": "29",
                        "AnoMateria": "2023",
                        "SiglaTipoPlOrcamento": "LOA",
                        "DescricaoTipoPlOrcamento": "Lei Orçamentária Anual",
                    }
                ]
            },
        }
    }

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/orcamento/lista.json",
            params={"ano": "2025"},
        ).respond(status_code=200, json=fake_response)

        df = await extractor.extract(ano=2025)

        assert df.height == 1
        assert "NomeAutorOrcamento" in df.columns
        assert "AnoExecucao" in df.columns


@pytest.mark.asyncio
async def test_emendas_extract_empty():
    """Envelope vazio → DataFrame vazio."""
    client = SenadoClient()
    extractor = OrcamentoEmendasExtractor(client)

    fake_response = {"ListaLoteEmendas": {"LotesEmendasOrcamento": {"LoteEmendasOrcamento": []}}}

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/orcamento/lista.json",
            params={"ano": "2025"},
        ).respond(status_code=200, json=fake_response)

        df = await extractor.extract(ano=2025)

        assert df.is_empty()


@pytest.mark.asyncio
async def test_emendas_extract_single_item_is_list():
    """API retorna objeto-único quando só 1 item — _ensure_list normaliza."""
    client = SenadoClient()
    extractor = OrcamentoEmendasExtractor(client)

    fake_response = {
        "ListaLoteEmendas": {
            "LotesEmendasOrcamento": {
                "LoteEmendasOrcamento": {
                    "NomeAutorOrcamento": "Único Autor",
                    "IndicadorAtivo": "Sim",
                }
            }
        }
    }

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/orcamento/lista.json",
            params={"ano": "2025"},
        ).respond(status_code=200, json=fake_response)

        df = await extractor.extract(ano=2025)

        assert df.height == 1


@pytest.mark.asyncio
async def test_emendas_extract_missing_data_path():
    """Path do envelope inexistente → DataFrame vazio."""
    client = SenadoClient()
    extractor = OrcamentoEmendasExtractor(client)

    fake_response = {"ListaLoteEmendas": {"Metadados": {}}}

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/orcamento/lista.json",
            params={"ano": "2025"},
        ).respond(status_code=200, json=fake_response)

        df = await extractor.extract(ano=2025)

        assert df.is_empty()


# ── ORCAMENTO_OFICIOS ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_oficios_extract_ano_returns_dataframe():
    """
    OrcamentoOficiosExtractor.extract(ano=2024) chama /orcamento/oficios
    e retorna DataFrame flat com o campo 'emendas' serializado.
    """
    client = SenadoClient()
    extractor = OrcamentoOficiosExtractor(client)

    fake_oficios = [
        {
            "id": 7905,
            "tratamento": "Deputado(a)",
            "nome": "Robinson Faria",
            "numeroProtocoloApresentacao": "CD261863719800",
            "dataInclusao": "2026-06-26T16:52:30.000+00:00",
            "emendas": [
                {
                    "id": 11496,
                    "numero": "202181000740",
                    "ano": "2021",
                    "autor": "RELATOR GERAL",
                }
            ],
        }
    ]

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/orcamento/oficios.json",
            params={"ano": "2024"},
        ).respond(status_code=200, json=fake_oficios)

        df = await extractor.extract(ano=2024)

        assert df.height == 1
        assert "id" in df.columns
        assert "nome" in df.columns
        assert "emendas" in df.columns


@pytest.mark.asyncio
async def test_oficios_extract_empty():
    """API retornando lista vazia → DataFrame vazio."""
    client = SenadoClient()
    extractor = OrcamentoOficiosExtractor(client)

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/orcamento/oficios.json",
            params={"ano": "2024"},
        ).respond(status_code=200, json=[])

        df = await extractor.extract(ano=2024)

        assert df.is_empty()


@pytest.mark.asyncio
async def test_oficios_extract_non_list():
    """API retornando dict (não lista) → DataFrame vazio."""
    client = SenadoClient()
    extractor = OrcamentoOficiosExtractor(client)

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/orcamento/oficios.json",
            params={"ano": "2024"},
        ).respond(status_code=200, json={"erro": "inesperado"})

        df = await extractor.extract(ano=2024)

        assert df.is_empty()


@pytest.mark.asyncio
async def test_oficios_extract_no_ano():
    """Ano omitido → chama sem query string."""
    client = SenadoClient()
    extractor = OrcamentoOficiosExtractor(client)

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/orcamento/oficios.json").respond(
            status_code=200, json=[]
        )

        df = await extractor.extract()

        assert df.is_empty()
