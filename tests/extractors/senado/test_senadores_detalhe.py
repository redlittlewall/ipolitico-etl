"""Testes do SenadoSenadoresDetalheExtractor — comportamento público."""

import polars as pl
import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.senadores_detalhe import (
    SenadoSenadoresDetalheExtractor,
)


@pytest.mark.asyncio
async def test_extract_entity_ids_returns_dataframe():
    """
    extract(entity_ids=[5672]) chama o endpoint correto, achata o envelope
    e retorna um DataFrame com os registros.
    """
    client = SenadoClient()
    extractor = SenadoSenadoresDetalheExtractor(client)

    fake_detail = {
        "IdentificacaoParlamentar": {
            "CodigoParlamentar": "5672",
            "NomeParlamentar": "Alan Rick",
            "NomeCompletoParlamentar": "Alan Rick Miranda",
            "SexoParlamentar": "Masculino",
            "UrlFotoParlamentar": "http://foto.jpg",
            "UrlPaginaParlamentar": "http://perfil",
            "EmailParlamentar": "alan@senado.leg.br",
        },
        "DadosBasicosParlamentar": {
            "DataNascimento": "1976-10-23",
            "Naturalidade": "Rio Branco",
            "UfNaturalidade": "AC",
        },
    }

    api_response = {
        "DetalheParlamentar": {
            "Parlamentar": fake_detail,
        }
    }

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/5672.json").respond(
            status_code=200, json=api_response
        )

        df = await extractor.extract(entity_ids=[5672])

        assert df.height == 1
        assert "IdentificacaoParlamentar" in df.columns
        assert "DadosBasicosParlamentar" in df.columns


@pytest.mark.asyncio
async def test_extract_multiple_senadores():
    """Múltiplos entity_ids produzem múltiplas linhas no DataFrame."""
    client = SenadoClient()
    extractor = SenadoSenadoresDetalheExtractor(client)

    with respx.mock:
        for codigo in [5672, 5982]:
            respx.get(f"https://legis.senado.leg.br/dadosabertos/senador/{codigo}.json").respond(
                status_code=200,
                json={
                    "DetalheParlamentar": {
                        "Parlamentar": {
                            "IdentificacaoParlamentar": {
                                "CodigoParlamentar": str(codigo),
                                "NomeParlamentar": f"Nome {codigo}",
                                "NomeCompletoParlamentar": f"Completo {codigo}",
                                "SexoParlamentar": "Masculino",
                                "UrlFotoParlamentar": f"http://foto{codigo}.jpg",
                                "UrlPaginaParlamentar": f"http://perfil{codigo}",
                                "EmailParlamentar": f"email{codigo}@senado.leg.br",
                            },
                            "DadosBasicosParlamentar": {
                                "DataNascimento": "1970-01-01",
                                "Naturalidade": "Brasília",
                                "UfNaturalidade": "DF",
                            },
                        }
                    }
                },
            )

        df = await extractor.extract(entity_ids=[5672, 5982])

        assert df.height == 2
        assert sorted(
            df["IdentificacaoParlamentar"]
            .struct.field("CodigoParlamentar")
            .cast(pl.Int64)
            .to_list()
        ) == [5672, 5982]


@pytest.mark.asyncio
async def test_extract_heterogeneous_structs_unifies_schema():
    """
    Senadores com structs aninhados de shapes diferentes não quebram o batch.

    O detalhe de um senador em exercício tem campos que o de um histórico não
    tem (ex: SexoParlamentar, EmailParlamentar). O extrator deve unificar o
    schema (união de campos, preenchendo com null) em vez de falhar no vstack.
    """
    client = SenadoClient()
    extractor = SenadoSenadoresDetalheExtractor(client)

    with respx.mock:
        # Senador ativo: IdentificacaoParlamentar mais rico
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/1.json").respond(
            status_code=200,
            json={
                "DetalheParlamentar": {
                    "Parlamentar": {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "1",
                            "NomeParlamentar": "Senador Um",
                            "SexoParlamentar": "Masculino",
                            "EmailParlamentar": "um@senado.leg.br",
                        },
                        "DadosBasicosParlamentar": {"DataNascimento": "1970-01-01"},
                    }
                }
            },
        )
        # Senador histórico: IdentificacaoParlamentar enxuto, DadosBasicos mais rico
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/2.json").respond(
            status_code=200,
            json={
                "DetalheParlamentar": {
                    "Parlamentar": {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "2",
                            "NomeParlamentar": "Senador Dois",
                        },
                        "DadosBasicosParlamentar": {
                            "DataNascimento": "1980-01-01",
                            "Naturalidade": "Brasília",
                            "UfNaturalidade": "DF",
                        },
                    }
                }
            },
        )

        df = await extractor.extract(entity_ids=[1, 2])

    assert df.height == 2

    # Schema união: campos dos dois senadores presentes no mesmo struct
    id_fields = {f.name for f in df.schema["IdentificacaoParlamentar"].fields}
    assert {"CodigoParlamentar", "NomeParlamentar", "SexoParlamentar", "EmailParlamentar"} <= id_fields
    basicos_fields = {f.name for f in df.schema["DadosBasicosParlamentar"].fields}
    assert {"DataNascimento", "Naturalidade", "UfNaturalidade"} <= basicos_fields

    # Campos ausentes viram null (não erro)
    assert df["IdentificacaoParlamentar"].struct.field("EmailParlamentar").to_list() == [
        "um@senado.leg.br",
        None,
    ]
    assert df["DadosBasicosParlamentar"].struct.field("Naturalidade").to_list() == [
        None,
        "Brasília",
    ]


@pytest.mark.asyncio
async def test_extract_empty_ids():
    """entity_ids vazio retorna DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoSenadoresDetalheExtractor(client)

    df = await extractor.extract(entity_ids=[])

    assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_404_returns_empty_skipped():
    """Senador inexistente (404) é ignorado sem quebrar o batch."""
    client = SenadoClient()
    extractor = SenadoSenadoresDetalheExtractor(client)

    with respx.mock:
        # Primeiro senador existe
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/1.json").respond(
            status_code=200,
            json={
                "DetalheParlamentar": {
                    "Parlamentar": {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "1",
                            "NomeParlamentar": "Senador Um",
                        },
                    }
                }
            },
        )
        # Segundo senador é 404
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/999.json").respond(
            status_code=404
        )

        df = await extractor.extract(entity_ids=[1, 999])

        # O 404 retorna [] do SenadoClient, que se torna vazio no flatten
        # O resultado tem apenas 1 registro
        assert df.height == 1
