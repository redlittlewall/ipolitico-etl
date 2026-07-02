"""Testes do SenadoMandatosExtractor — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.senadores import SenadoMandatosExtractor


@pytest.mark.asyncio
async def test_extract_with_codigo_returns_dataframe():
    """
    extract(codigo=5672) chama o endpoint correto, achata o envelope real
    (``MandatoParlamentar.Parlamentar.Mandatos.Mandato``), injeta
    ``CodigoParlamentar`` e retorna um DataFrame com os mandatos do senador.
    """
    client = SenadoClient()
    extractor = SenadoMandatosExtractor(client)

    api_response = {
        "MandatoParlamentar": {
            "Parlamentar": {
                "Codigo": "5672",
                "Nome": "Alan Rick",
                "Mandatos": {
                    "Mandato": [
                        {
                            "CodigoMandato": "1001",
                            "UfParlamentar": "AC",
                            "PrimeiraLegislaturaDoMandato": {
                                "NumeroLegislatura": "57",
                                "DataInicio": "2023-02-01",
                                "DataFim": "2027-01-31",
                            },
                            "SegundaLegislaturaDoMandato": {
                                "NumeroLegislatura": "57",
                                "DataInicio": "2023-02-01",
                                "DataFim": "2027-01-31",
                            },
                            "DescricaoParticipacao": "Titular",
                        },
                        {
                            "CodigoMandato": "1002",
                            "UfParlamentar": "AC",
                            "PrimeiraLegislaturaDoMandato": {
                                "NumeroLegislatura": "56",
                                "DataInicio": "2019-02-01",
                                "DataFim": "2023-01-31",
                            },
                            "SegundaLegislaturaDoMandato": {
                                "NumeroLegislatura": "56",
                                "DataInicio": "2019-02-01",
                                "DataFim": "2023-01-31",
                            },
                            "DescricaoParticipacao": "Suplente",
                        },
                    ],
                },
            },
        },
    }

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/5672/mandatos.json").respond(
            status_code=200, json=api_response
        )

        df = await extractor.extract(codigo=5672)

        assert not df.is_empty()
        assert df.height == 2
        assert "CodigoMandato" in df.columns
        assert "CodigoParlamentar" in df.columns
        assert df["CodigoMandato"].to_list() == ["1001", "1002"]
        assert df["CodigoParlamentar"].to_list() == ["5672", "5672"]
        assert "PrimeiraLegislaturaDoMandato" in df.columns


@pytest.mark.asyncio
async def test_extract_without_codigo_returns_empty():
    """extract() sem codigo retorna DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoMandatosExtractor(client)

    df = await extractor.extract()

    assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_404_returns_empty():
    """Senador inexistente (404) retorna DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoMandatosExtractor(client)

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/999/mandatos.json").respond(
            status_code=404
        )

        df = await extractor.extract(codigo=999)

        assert df.is_empty()
