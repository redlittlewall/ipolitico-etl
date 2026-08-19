"""Testes do PortalServidoresPorOrgaoApiExtractor — cg_servidores via API v3.

Prior art: ``tests/extractors/portal_transparencia/api/test_orgaos_extractor.py``
— o agregado ``/servidores/por-orgao`` (validado no ticket 03) página o mesmo
jeito: page_size fixo 15, ``_source_page`` por registro, ``_source_url``
replayável por página. O DTO tem 13 campos: contagens (``qntPessoas``/
``qntVinculos``), dimensões por chave SK (situação/tipo de vínculo/tipo de
servidor) e o órgão SIAPE de exercício (código como String, preserva zeros).
"""

from unittest.mock import AsyncMock

import pytest

from ipolitico.core.config import PORTAL_API_BASE_URL
from ipolitico.extractors.portal_transparencia.api.servidores_por_orgao_extractor import (
    PortalServidoresPorOrgaoApiExtractor,
)

API_BASE = PORTAL_API_BASE_URL.rstrip("/")
ENDPOINT = "api-de-dados/servidores/por-orgao"


@pytest.fixture
def mock_client():
    """Cliente com ``fetch`` mockado (a API v3 retorna lista top-level)."""
    client = AsyncMock()
    client.BASE_URL = PORTAL_API_BASE_URL
    return client


def _row(orgao: str, situacao: int = 1) -> dict:
    """Uma linha do agregado por-orgao como a API devolve."""
    return {
        "qntPessoas": 1,
        "qntVinculos": 1,
        "skSituacao": situacao,
        "descSituacao": "Ativo",
        "skTipoVinculo": 3,
        "descTipoVinculo": "Outros",
        "skTipoServidor": 1,
        "descTipoServidor": "Civil",
        "licenca": 0,
        "codOrgaoExercicioSiape": orgao,
        "nomOrgaoExercicioSiape": f"ORGAO {orgao}",
        "codOrgaoSuperiorExercicioSiape": "60000",
        "nomOrgaoSuperiorExercicioSiape": "PRESIDENCIA",
    }


def test_endpoint_constante():
    """O extrator aponta para o endpoint real do agregado na API v3."""
    assert PortalServidoresPorOrgaoApiExtractor.ENDPOINT == ENDPOINT


@pytest.mark.asyncio
async def test_extract_pagina_todas_as_paginas(mock_client):
    """Percorre páginas até a última (curta): 15 + 10 = 25 registros."""
    page1 = [_row(f"{i:05d}") for i in range(1, 16)]
    page2 = [_row(f"{i:05d}") for i in range(16, 26)]

    async def fake_fetch(endpoint, params=None):
        assert endpoint == ENDPOINT
        page = (params or {}).get("pagina", 1)
        return page1 if page == 1 else page2

    mock_client.fetch.side_effect = fake_fetch
    ext = PortalServidoresPorOrgaoApiExtractor(mock_client)

    result = await ext.extract()

    assert result.height == 25
    assert result["codOrgaoExercicioSiape"].to_list() == [f"{i:05d}" for i in range(1, 26)]
    assert result["_source_url"].to_list() == [
        f"{API_BASE}/{ENDPOINT}?pagina=1"
    ] * 15 + [f"{API_BASE}/{ENDPOINT}?pagina=2"] * 10


@pytest.mark.asyncio
async def test_extract_api_vazia_retorna_vazio(mock_client):
    """API sem dados (404/lista vazia) → DataFrame vazio, sem crash."""
    mock_client.fetch.return_value = []
    ext = PortalServidoresPorOrgaoApiExtractor(mock_client)

    result = await ext.extract()

    assert result.is_empty()


@pytest.mark.asyncio
async def test_extract_preserva_zero_a_esquerda_do_orgao(mock_client):
    """``codOrgaoExercicioSiape`` permanece String no raw (zeros à esquerda)."""
    async def fake_fetch(endpoint, params=None):
        page = (params or {}).get("pagina", 1)
        return [_row("081300")] if page == 1 else []

    mock_client.fetch.side_effect = fake_fetch
    ext = PortalServidoresPorOrgaoApiExtractor(mock_client)

    result = await ext.extract()

    assert result["codOrgaoExercicioSiape"].to_list() == ["081300"]
    assert result["skTipoServidor"].to_list() == [1]
