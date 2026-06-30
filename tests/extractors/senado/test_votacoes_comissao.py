"""Testes do SenadoVotacoesComissaoExtractor — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.votacoes_comissao import SenadoVotacoesComissaoExtractor


@pytest.mark.asyncio
async def test_extract_with_params():
    """
    extract(sigla_comissao="CAE", start_date="2025-01-01", end_date="2025-01-31")
    chama /votacaoComissao/comissao/CAE com dataInicio/dataFim e retorna DataFrame.
    """
    client = SenadoClient()
    extractor = SenadoVotacoesComissaoExtractor(client)

    fake_votacoes = [
        {
            "codigoSessaoVotacao": 1045,
            "codigoMateria": 167447,
            "idProcesso": 8799208,
            "identificacao": "PL 123/2025",
            "ementa": "Dispõe sobre...",
            "dataApresentacao": "2025-03-06",
            "dataSessao": "2025-07-01",
            "descricaoVotacao": "Votação nominal...",
            "resultadoVotacao": "A",
            "siglaComissao": "CAE",
        }
    ]

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/votacaoComissao/comissao/CAE.json",
            params={"dataInicio": "2025-01-01", "dataFim": "2025-01-31"},
        ).respond(status_code=200, json=fake_votacoes)

        df = await extractor.extract(
            sigla_comissao="CAE",
            start_date="2025-01-01",
            end_date="2025-01-31",
        )

        assert df.height == 1
        assert "identificacao" in df.columns
        assert df["identificacao"][0] == "PL 123/2025"


@pytest.mark.asyncio
async def test_extract_no_params():
    """Sem parâmetros de data, chama o endpoint sem query string."""
    client = SenadoClient()
    extractor = SenadoVotacoesComissaoExtractor(client)

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/votacaoComissao/comissao/CAE.json",
        ).respond(status_code=200, json=[])

        df = await extractor.extract(sigla_comissao="CAE")

        assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_empty_response():
    """API retornando lista vazia → DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoVotacoesComissaoExtractor(client)

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/votacaoComissao/comissao/CAE.json",
            params={"dataInicio": "2025-01-01", "dataFim": "2025-01-31"},
        ).respond(status_code=200, json=[])

        df = await extractor.extract(
            sigla_comissao="CAE",
            start_date="2025-01-01",
            end_date="2025-01-31",
        )

        assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_invalid_response():
    """API retornando dict não-lista → DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoVotacoesComissaoExtractor(client)

    with respx.mock:
        respx.get(
            "https://legis.senado.leg.br/dadosabertos/votacaoComissao/comissao/CAE.json",
        ).respond(status_code=200, json={"erro": "inesperado"})

        df = await extractor.extract(sigla_comissao="CAE")

        assert df.is_empty()
