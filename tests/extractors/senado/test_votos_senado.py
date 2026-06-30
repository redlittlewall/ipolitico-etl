"""Testes do SenadoVotosExtractor — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.votos_senado import SenadoVotosExtractor


@pytest.mark.asyncio
async def test_extract_votos_from_votacao():
    """
    extract(year=2025) chama /votacao?ano=2025, extrai o array votos[]
    de cada votação e injeta codigoSessaoVotacao em cada voto.
    """
    client = SenadoClient()
    extractor = SenadoVotosExtractor(client)

    fake_votacoes = [
        {
            "codigoSessaoVotacao": 6954,
            "votos": [
                {"codigoParlamentar": 5672, "siglaVotoParlamentar": "Sim"},
                {"codigoParlamentar": 5982, "siglaVotoParlamentar": "Não"},
            ],
        }
    ]

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/votacao.json",
            params={"ano": "2025"},
        ).respond(status_code=200, json=fake_votacoes)

        df = await extractor.extract(year=2025)

        assert df.height == 2
        assert "codigoSessaoVotacao" in df.columns
        # Ambos os votos herdaram o ID da votação
        assert df["codigoSessaoVotacao"].to_list() == [6954, 6954]


@pytest.mark.asyncio
async def test_extract_empty_votacoes():
    """Sem votações no ano → DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoVotosExtractor(client)

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/votacao.json",
            params={"ano": "2000"},
        ).respond(status_code=200, json=[])

        df = await extractor.extract(year=2000)

        assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_votacao_without_votos():
    """Votação sem campo votos → é ignorada."""
    client = SenadoClient()
    extractor = SenadoVotosExtractor(client)

    fake_votacoes = [
        {"codigoSessaoVotacao": 6954}  # sem votos
    ]

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/votacao.json",
            params={"ano": "2025"},
        ).respond(status_code=200, json=fake_votacoes)

        df = await extractor.extract(year=2025)

        assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_multiple_votacoes():
    """Múltiplas votações com votos são achatadas corretamente."""
    client = SenadoClient()
    extractor = SenadoVotosExtractor(client)

    fake_votacoes = [
        {
            "codigoSessaoVotacao": 1001,
            "votos": [
                {"codigoParlamentar": 1, "siglaVotoParlamentar": "Sim"},
            ],
        },
        {
            "codigoSessaoVotacao": 1002,
            "votos": [
                {"codigoParlamentar": 2, "siglaVotoParlamentar": "Não"},
                {"codigoParlamentar": 3, "siglaVotoParlamentar": "Abstenção"},
            ],
        },
    ]

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/votacao.json",
            params={"ano": "2025"},
        ).respond(status_code=200, json=fake_votacoes)

        df = await extractor.extract(year=2025)

        assert df.height == 3
        assert df["codigoSessaoVotacao"].to_list() == [1001, 1002, 1002]
