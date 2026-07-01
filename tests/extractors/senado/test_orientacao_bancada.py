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
    /plenario/votacao/orientacaoBancada/20250101/20250131 e retorna DataFrame
    com o envelope ``{"votacoes": [...]}`` desenvelopado.
    """
    client = SenadoClient()
    extractor = SenadoOrientacaoBancadaExtractor(client)

    fake_response = {
        "votacoes": [
            {
                "codigoVotacaoSve": 10848,
                "dataInicioVotacao": "2025-01-15T14:00:00",
                "orientacoesLideranca": [
                    {"dataHora": "2025-01-15T14:10:00", "partido": "PT", "voto": "Sim"},
                    {"dataHora": "2025-01-15T14:10:05", "partido": "PL", "voto": "Não"},
                ],
            },
        ],
    }

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/plenario/votacao/orientacaoBancada/20250101/20250131.json",
        ).respond(status_code=200, json=fake_response)

        df = await extractor.extract(start_date="2025-01-01", end_date="2025-01-31")

        assert df.height == 1  # 1 votação (orientacoesLideranca preserved)
        assert "orientacoesLideranca" in df.columns
        assert "codigoVotacaoSve" in df.columns


@pytest.mark.asyncio
async def test_extract_empty_list():
    """API retornando lista vazia no envelope → DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoOrientacaoBancadaExtractor(client)

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/plenario/votacao/orientacaoBancada/20000101/20000131.json",
        ).respond(status_code=200, json={"votacoes": []})

        df = await extractor.extract(start_date="2000-01-01", end_date="2000-01-31")

        assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_no_votacoes_key():
    """API retornando dict sem chave ``votacoes`` → DataFrame vazio."""
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
