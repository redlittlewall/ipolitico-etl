import pytest
import respx
from httpx import Response
from ipolitico.core.client import CamaraClient
from ipolitico.extractors.camara.api.eventos import EventosExtractor
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
