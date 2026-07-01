"""Testes do SenadoFiliacoesExtractor — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.senadores import SenadoFiliacoesExtractor


@pytest.mark.asyncio
async def test_extract_with_codigo_returns_dataframe():
    """
    extract(codigo=5672) chama o endpoint correto, achata o envelope real
    (``FiliacaoParlamentar.Parlamentar.Filiacoes.Filiacao``), injeta
    ``CodigoParlamentar`` e retorna um DataFrame com as filiações do senador.
    """
    client = SenadoClient()
    extractor = SenadoFiliacoesExtractor(client)

    api_response = {
        "FiliacaoParlamentar": {
            "Parlamentar": {
                "Codigo": "5672",
                "Nome": "Alan Rick",
                "Filiacoes": {
                    "Filiacao": [
                        {
                            "Partido": {
                                "SiglaPartido": "PP",
                                "DataFiliacao": "2020-03-10",
                                "DataDesfiliacao": None,
                            },
                        },
                        {
                            "Partido": {
                                "SiglaPartido": "PSDB",
                                "DataFiliacao": "2015-02-01",
                                "DataDesfiliacao": "2020-03-09",
                            },
                        },
                    ],
                },
            },
        },
    }

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/5672/filiacoes.json").respond(
            status_code=200, json=api_response
        )

        df = await extractor.extract(codigo=5672)

        assert not df.is_empty()
        assert df.height == 2
        assert "Partido" in df.columns  # struct nested
        assert "CodigoParlamentar" in df.columns
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
