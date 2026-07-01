"""Testes do SenadoOrientacaoBancadaExtractor — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.orientacao_bancada import (
    SenadoOrientacaoBancadaExtractor,
)


@pytest.mark.asyncio
async def test_extract_with_dates():
    """
    extract(start_date="2025-01-01", end_date="2025-01-31") chama
    /plenario/votacao/orientacaoBancada/20250101/20250131 e retorna DataFrame.
    """
    client = SenadoClient()
    extractor = SenadoOrientacaoBancadaExtractor(client)

    fake_orientacoes = [
        {
            "dataSessao": "2025-01-15",
            "codigoMateria": 167447,
            "siglaPartido": "PT",
            "orientacao": "Sim",
            "codigoVotacao": 6954,
        },
        {
            "dataSessao": "2025-01-15",
            "codigoMateria": 167447,
            "siglaPartido": "PL",
            "orientacao": "Não",
            "codigoVotacao": 6954,
        },
    ]

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/plenario/votacao/orientacaoBancada/20250101/20250131.json",
        ).respond(status_code=200, json=fake_orientacoes)

        df = await extractor.extract(start_date="2025-01-01", end_date="2025-01-31")

        assert df.height == 2
        assert "siglaPartido" in df.columns
        assert df["orientacao"][0] == "Sim"


@pytest.mark.asyncio
async def test_extract_empty_list():
    """API retornando lista vazia → DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoOrientacaoBancadaExtractor(client)

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/plenario/votacao/orientacaoBancada/20000101/20000131.json",
        ).respond(status_code=200, json=[])

        df = await extractor.extract(start_date="2000-01-01", end_date="2000-01-31")

        assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_invalid_response():
    """API retornando dict em vez de lista → DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoOrientacaoBancadaExtractor(client)

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/plenario/votacao/orientacaoBancada/20250101/20250131.json",
        ).respond(status_code=200, json={"erro": "inesperado"})

        df = await extractor.extract(start_date="2025-01-01", end_date="2025-01-31")

        assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_no_dates():
    """Sem start_date/end_date, retorna DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoOrientacaoBancadaExtractor(client)

    df = await extractor.extract()

    assert df.is_empty()
