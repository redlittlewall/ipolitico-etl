import pytest
import respx
from httpx import Response

from ipolitico.core.camara_client import CamaraClient
from ipolitico.extractors.camara.api.blocos import BlocosExtractor
from ipolitico.extractors.camara.api.eventos import EventosExtractor
from ipolitico.extractors.camara.api.frentes import FrentesExtractor
from ipolitico.extractors.camara.api.grupos import GruposExtractor
from ipolitico.extractors.camara.api.legislaturas import LegislaturasExtractor
from ipolitico.extractors.camara.api.orgaos import OrgaosExtractor
from ipolitico.extractors.camara.api.partidos import PartidosExtractor


@pytest.mark.asyncio
@respx.mock
async def test_orgaos_extractor_paginated():
    respx.get("https://dadosabertos.camara.leg.br/api/v2/orgaos").mock(
        return_value=Response(
            200,
            json={
                "dados": [{"id": 1, "sigla": "PLEN", "nome": "Plenário", "uri": "u"}],
                "links": [],
            },
        )
    )
    ext = OrgaosExtractor(CamaraClient())
    df = await ext.extract(start_date="2024-01-01", end_date="2024-01-31")
    await ext.client.close()
    assert df.height == 1
    assert df["_source_url"][0] == "https://dadosabertos.camara.leg.br/api/v2/orgaos/1"


@pytest.mark.asyncio
@respx.mock
async def test_partidos_extractor():
    respx.get("https://dadosabertos.camara.leg.br/api/v2/partidos").mock(
        return_value=Response(
            200,
            json={"dados": [{"id": 10, "sigla": "PT", "nome": "PT", "uri": "u"}], "links": []},
        )
    )
    ext = PartidosExtractor(CamaraClient())
    df = await ext.extract(start_date="2024-01-01", end_date="2024-12-31", legislatura_id=57)
    await ext.client.close()
    assert df.height == 1
    assert df["_source_url"][0] == "https://dadosabertos.camara.leg.br/api/v2/partidos/10"


@pytest.mark.asyncio
@respx.mock
async def test_eventos_extractor():
    respx.get("https://dadosabertos.camara.leg.br/api/v2/eventos").mock(
        return_value=Response(
            200,
            json={
                "dados": [
                    {
                        "id": 99,
                        "uri": "u",
                        "descricao": "Sessão",
                        "dataHoraInicio": "2024-03-01T14:00",
                    }
                ],
                "links": [],
            },
        )
    )
    ext = EventosExtractor(CamaraClient())
    df = await ext.extract(start_date="2024-03-01", end_date="2024-03-31")
    await ext.client.close()
    assert df.height == 1
    assert df["_source_url"][0] == "https://dadosabertos.camara.leg.br/api/v2/eventos/99"


@pytest.mark.asyncio
@respx.mock
async def test_blocos_extractor():
    respx.get("https://dadosabertos.camara.leg.br/api/v2/blocos").mock(
        return_value=Response(
            200,
            json={
                "dados": [{"id": 1, "nome": "Bloco A", "uri": "u", "idLegislatura": 57}],
                "links": [],
            },
        )
    )
    ext = BlocosExtractor(CamaraClient())
    df = await ext.extract(start_date="2024-01-01", end_date="2024-12-31", legislatura_id=57)
    await ext.client.close()
    assert df.height == 1
    assert df["_source_url"][0] == "https://dadosabertos.camara.leg.br/api/v2/blocos/1"


@pytest.mark.asyncio
@respx.mock
async def test_frentes_extractor():
    respx.get("https://dadosabertos.camara.leg.br/api/v2/frentes").mock(
        return_value=Response(
            200,
            json={
                "dados": [{"id": 10, "titulo": "Frente A", "uri": "u", "idLegislatura": 57}],
                "links": [],
            },
        )
    )
    ext = FrentesExtractor(CamaraClient())
    df = await ext.extract(start_date="2024-01-01", end_date="2024-12-31", legislatura_id=57)
    await ext.client.close()
    assert df.height == 1
    assert df["_source_url"][0] == "https://dadosabertos.camara.leg.br/api/v2/frentes/10"


@pytest.mark.asyncio
@respx.mock
async def test_grupos_extractor():
    respx.get("https://dadosabertos.camara.leg.br/api/v2/grupos").mock(
        return_value=Response(
            200,
            json={
                "dados": [
                    {
                        "id": 1,
                        "nome": "Grupo A",
                        "uri": "u",
                        "anoCriacao": "2023",
                        "ativo": "Sim",
                        "ultimoStatus": {"codSituacao": 1, "descricao": "Ativo"},
                    }
                ],
                "links": [],
            },
        )
    )
    ext = GruposExtractor(CamaraClient())
    df = await ext.extract(start_date="2024-01-01", end_date="2024-12-31")
    await ext.client.close()
    assert df.height == 1
    assert df["_source_url"][0] == "https://dadosabertos.camara.leg.br/api/v2/grupos/1"


@pytest.mark.asyncio
@respx.mock
async def test_legislaturas_extractor():
    respx.get("https://dadosabertos.camara.leg.br/api/v2/legislaturas").mock(
        return_value=Response(
            200,
            json={
                "dados": [
                    {
                        "id": 57,
                        "uri": "u",
                        "dataInicio": "2023-02-01",
                        "dataFim": "2027-01-31",
                    }
                ],
                "links": [],
            },
        )
    )
    ext = LegislaturasExtractor(CamaraClient())
    df = await ext.extract(start_date="2023-01-01", end_date="2026-12-31")
    await ext.client.close()
    assert df.height == 1
    assert df["_source_url"][0] == "https://dadosabertos.camara.leg.br/api/v2/legislaturas/57"
