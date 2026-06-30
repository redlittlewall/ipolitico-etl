"""Testes do SenadoProcessosExtractor — comportamento público."""

import pytest
import respx

from ipolitico.core.senado_client import SenadoClient
from ipolitico.extractors.senado.api.processos import SenadoProcessosExtractor


@pytest.mark.asyncio
async def test_extract_returns_dataframe():
    """
    extract() chama o endpoint /processo e retorna um DataFrame
    com os campos flat da API.
    """
    client = SenadoClient()
    extractor = SenadoProcessosExtractor(client)

    fake_processos = [
        {
            "id": 1326805,
            "codigoMateria": 603,
            "identificacao": "PDS 16/1984",
            "ementa": "Aprova o texto da Convenção...",
            "autoria": "Câmara dos Deputados",
            "tipoDocumento": "Projeto de Decreto Legislativo",
            "dataApresentacao": "1949-05-31",
            "situacaoAtual": "MATÉRIA COM A RELATORIA",
            "dataSituacaoAtual": "2023-03-23",
            "casaIdentificadora": "SF",
            "tramitando": "Sim",
        }
    ]

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/processo.json").respond(
            status_code=200, json=fake_processos
        )

        df = await extractor.extract()

        assert df.height == 1
        assert "id" in df.columns
        assert "identificacao" in df.columns


@pytest.mark.asyncio
async def test_extract_empty_list():
    """API retornando lista vazia → DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoProcessosExtractor(client)

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/processo.json").respond(
            status_code=200, json=[]
        )

        df = await extractor.extract()

        assert df.is_empty()


@pytest.mark.asyncio
async def test_extract_non_list_response():
    """API retornando dict (não lista) → DataFrame vazio."""
    client = SenadoClient()
    extractor = SenadoProcessosExtractor(client)

    with respx.mock:
        respx.get("https://legis.senado.leg.br/dadosabertos/processo.json").respond(
            status_code=200, json={"erro": "inesperado"}
        )

        df = await extractor.extract()

        assert df.is_empty()
