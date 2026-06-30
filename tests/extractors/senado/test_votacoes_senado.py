"""Testes do SenadoVotacoesExtractor — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.votacoes_senado import SenadoVotacoesExtractor


@pytest.mark.asyncio
async def test_extract_with_year():
    """
    extract(year=2025) chama /votacao?ano=2025 e retorna DataFrame.
    """
    client = SenadoClient()
    extractor = SenadoVotacoesExtractor(client)

    fake_votacoes = [
        {
            "codigoSessaoVotacao": 6954,
            "codigoMateria": 167447,
            "idProcesso": 8799208,
            "identificacao": "MPV 1291/2025",
            "ementa": "Altera a Lei...",
            "dataApresentacao": "2025-03-06",
            "dataSessao": "2025-07-01",
            "descricaoVotacao": "Votação nominal...",
            "resultadoVotacao": "A",
            "votos": [{"codigoParlamentar": 5672}],
        }
    ]

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/votacao.json",
            params={"ano": "2025"},
        ).respond(status_code=200, json=fake_votacoes)

        df = await extractor.extract(year=2025)

        assert df.height == 1
        assert "identificacao" in df.columns


@pytest.mark.asyncio
async def test_extract_empty_list():
    """API retornando lista vazia → DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoVotacoesExtractor(client)

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/votacao.json",
            params={"ano": "2000"},
        ).respond(status_code=200, json=[])

        df = await extractor.extract(year=2000)

        assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_invalid_response():
    """API retornando dict → DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoVotacoesExtractor(client)

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/votacao.json",
            params={"ano": "2025"},
        ).respond(status_code=200, json={"erro": "inesperado"})

        df = await extractor.extract(year=2025)

        assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_no_year_uses_current():
    """Sem year, usa o ano corrente (não quebra)."""
    client = SenadoClient()
    extractor = SenadoVotacoesExtractor(client)

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/votacao.json",
        ).respond(status_code=200, json=[])

        df = await extractor.extract()

        assert df.is_empty()
