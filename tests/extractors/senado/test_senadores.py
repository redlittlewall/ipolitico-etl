"""Testes do SenadoSenadoresExtractor — comportamento público, não implementação."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.senadores import SenadoSenadoresExtractor


@pytest.mark.asyncio
async def test_extract_by_legislature_returns_dataframe():
    """
    extract(legislatura_id=57) chama o endpoint correto, achata o envelope
    XML-heritage e retorna um DataFrame com os registros.
    """
    client = SenadoClient()
    extractor = SenadoSenadoresExtractor(client)

    fake_senadores = [
        {
            "IdentificacaoParlamentar": {
                "CodigoParlamentar": "5918",
                "NomeParlamentar": "Adilson Gomes",
                "NomeCompletoParlamentar": "Adilson Gomes Silva",
                "SexoParlamentar": "Masculino",
            },
            "Mandatos": {
                "Mandato": [
                    {
                        "CodigoMandato": "526",
                        "UfParlamentar": "PE",
                        "DescricaoParticipacao": "Titular",
                        "PrimeiraLegislaturaDoMandato": {"NumeroLegislatura": "56"},
                        "SegundaLegislaturaDoMandato": {"NumeroLegislatura": "57"},
                    }
                ]
            },
        }
    ]
    api_response = {
        "ListaParlamentarLegislatura": {
            "Parlamentares": {
                "Parlamentar": fake_senadores,
            }
        }
    }

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/57.json"
        ).respond(status_code=200, json=api_response)

        df = await extractor.extract(legislatura_id=57)

        assert df.height == 1
        # O DataFrame cru preserva os dicionários aninhados
        assert "IdentificacaoParlamentar" in df.columns
        assert "Mandatos" in df.columns


@pytest.mark.asyncio
async def test_extract_no_legislatura_uses_atual():
    """
    extract() sem legislatura_id chama o endpoint /atual.
    """
    client = SenadoClient()
    extractor = SenadoSenadoresExtractor(client)

    api_response = {
        "ListaParlamentarEmExercicio": {
            "Parlamentares": {
                "Parlamentar": [
                    {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": "5672",
                            "NomeParlamentar": "Alan Rick",
                        }
                    }
                ]
            }
        }
    }

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json").respond(
            status_code=200, json=api_response
        )

        df = await extractor.extract()

        assert df.height == 1


@pytest.mark.asyncio
async def test_extract_empty_response():
    """
    Quando a API retorna um envelope sem o array alvo, retorna DataFrame vazio.
    """
    client = SenadoClient()
    extractor = SenadoSenadoresExtractor(client)

    api_response = {"ListaParlamentarLegislatura": {}}

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/57.json"
        ).respond(status_code=200, json=api_response)

        df = await extractor.extract(legislatura_id=57)

        assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_404_returns_empty():
    """
    Falso 404: legislatura sem senadores retorna DataFrame vazio.
    """
    client = SenadoClient()
    extractor = SenadoSenadoresExtractor(client)

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/99.json"
        ).respond(status_code=404)

        df = await extractor.extract(legislatura_id=99)

        assert df.is_empty()
