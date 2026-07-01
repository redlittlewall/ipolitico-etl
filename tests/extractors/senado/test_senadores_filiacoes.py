"""Testes do SenadoFiliacoesExtractor — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.senadores import SenadoFiliacoesExtractor


@pytest.mark.asyncio
async def test_extract_with_codigo_returns_dataframe():
    """
    extract(codigo=5672) chama o endpoint correto, achata o envelope XML-heritage,
    injeta CodigoParlamentar e retorna um DataFrame com as filiações do senador.
    """
    client = SenadoClient()
    extractor = SenadoFiliacoesExtractor(client)

    fake_filiacoes = [
        {
            "SiglaPartido": "PP",
            "DataFiliacao": "2020-03-10",
            "DataDesfiliacao": "",
        },
        {
            "SiglaPartido": "PSDB",
            "DataFiliacao": "2015-02-01",
            "DataDesfiliacao": "2020-03-09",
        },
    ]

    api_response = {
        "MembroParlamentar": {
            "IdentificacaoParlamentar": {
                "CodigoParlamentar": "5672",
                "NomeParlamentar": "Alan Rick",
            },
            "Filiacoes": {
                "Filiacao": fake_filiacoes,
            },
        }
    }

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/5672/filiacoes.json").respond(
            status_code=200, json=api_response
        )

        df = await extractor.extract(codigo=5672)

        assert not df.is_empty()
        assert df.height == 2
        assert "SiglaPartido" in df.columns
        assert "DataFiliacao" in df.columns
        assert "CodigoParlamentar" in df.columns
        assert df["SiglaPartido"].to_list() == ["PP", "PSDB"]
        assert df["CodigoParlamentar"].to_list() == ["5672", "5672"]


@pytest.mark.asyncio
async def test_extract_without_codigo_returns_empty():
    """extract() sem codigo retorna DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoFiliacoesExtractor(client)

    df = await extractor.extract()

    assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_404_returns_empty():
    """Senador inexistente (404) retorna DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoFiliacoesExtractor(client)

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/999/filiacoes.json").respond(
            status_code=404
        )

        df = await extractor.extract(codigo=999)

        assert df.is_empty()
