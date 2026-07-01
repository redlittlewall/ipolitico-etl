"""Testes do SenadoMandatosExtractor — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.senadores import SenadoMandatosExtractor


@pytest.mark.asyncio
async def test_extract_with_codigo_returns_dataframe():
    """
    extract(codigo=5672) chama o endpoint correto, achata o envelope XML-heritage,
    injeta CodigoParlamentar e retorna um DataFrame com os mandatos do senador.
    """
    client = SenadoClient()
    extractor = SenadoMandatosExtractor(client)

    fake_mandatos = [
        {
            "CodigoMandato": "1001",
            "Uf": "AC",
            "DescricaoParticipacao": "Titular",
            "PrimeiraLegislatura": "57",
            "SegundaLegislatura": "57",
            "SiglaPartido": "PP",
            "DataInicio": "2023-02-01",
            "DataFim": "2027-01-31",
        },
        {
            "CodigoMandato": "1002",
            "Uf": "AC",
            "DescricaoParticipacao": "Suplente",
            "PrimeiraLegislatura": "56",
            "SegundaLegislatura": "56",
            "SiglaPartido": "PP",
            "DataInicio": "2019-02-01",
            "DataFim": "2023-01-31",
        },
    ]

    api_response = {
        "MembroParlamentar": {
            "IdentificacaoParlamentar": {
                "CodigoParlamentar": "5672",
                "NomeParlamentar": "Alan Rick",
            },
            "Mandatos": {
                "Mandato": fake_mandatos,
            },
        }
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
