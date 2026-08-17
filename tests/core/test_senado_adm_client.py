"""Testes do SenadoAdmClient — comportamento público, não implementação (issue 06).

Prior art: ``tests/core/test_senado_client.py`` — client mockado via ``respx``.
"""

import asyncio
from unittest.mock import patch

import httpx
import pytest
import respx

from ipolitico.core.config import SENADO_ADM_API_BASE_URL
from ipolitico.core.senado_adm_client import SenadoAdmAPIError, SenadoAdmClient


def _url(endpoint: str) -> str:
    """Monta a URL completa da API adm-dadosabertos para as rotas respx."""
    return f"{SENADO_ADM_API_BASE_URL}/{endpoint.lstrip('/')}"


@pytest.mark.asyncio
async def test_senado_adm_client_returns_top_level_list():
    """
    Shape agnóstico: lista top-level (servidores/*, despesas_ceaps/*)
    devolvida como veio — sem normalização de envelope no client.
    """
    client = SenadoAdmClient()
    payload = [
        {"sequencial": 1, "nome": "FULANO DE TAL"},
        {"sequencial": 2, "nome": "BELTRANO"},
    ]

    with respx.mock:
        respx.get(_url("servidores/servidores")).respond(200, json=payload)
        result = await client.fetch("servidores/servidores")

    assert result == payload


@pytest.mark.asyncio
async def test_senado_adm_client_returns_envelope_unchanged():
    """
    Shape agnóstico: envelope ``{statusCode, msg, data}`` (senadores, gestao/*)
    devolvido como veio — a normalização fica no extrator/transformer do domínio.
    """
    client = SenadoAdmClient()
    envelope = {"statusCode": 200, "msg": "Sucesso", "data": [{"codigo": 22, "nome": "X"}]}

    with respx.mock:
        respx.get(_url("senadores")).respond(200, json=envelope)
        result = await client.fetch("senadores")

    assert result == envelope
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_senado_adm_client_404_returns_empty_list():
    """
    404 = ausência (mês/ano sem dados), não exceção: lista vazia, sem retry
    (mesmo padrão do SenadoClient).
    """
    client = SenadoAdmClient()

    with respx.mock:
        route = respx.get(_url("servidores/remuneracoes/2012/12")).respond(404)
        result = await client.fetch("servidores/remuneracoes/2012/12")

    assert isinstance(result, list)
    assert result == []
    assert route.call_count == 1  # sem retry em 404


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_senado_adm_client_retries_on_429_then_success(mock_sleep):
    """
    Retry cobre HTTP 429 (throttling): sucesso na segunda tentativa.
    """
    client = SenadoAdmClient(max_retries=3)
    payload = [{"sequencial": 1, "nome": "FULANO"}]

    with respx.mock:
        respx.get(_url("servidores/servidores")).mock(
            side_effect=[httpx.Response(429), httpx.Response(200, json=payload)]
        )
        result = await client.fetch("servidores/servidores")

    assert result == payload


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_senado_adm_client_retries_on_5xx_then_success(mock_sleep):
    """
    Retry cobre HTTP 5xx (ex: 503 da API): sucesso na segunda tentativa.
    """
    client = SenadoAdmClient(max_retries=3)
    payload = [{"ano": 2013, "mes": 1, "nome": "FULANO"}]

    with respx.mock:
        respx.get(_url("servidores/remuneracoes/2013/1")).mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json=payload)]
        )
        result = await client.fetch("servidores/remuneracoes/2013/1")

    assert result == payload


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_senado_adm_client_retries_on_network_error_then_success(mock_sleep):
    """
    Retry cobre erro de rede/SSL transiente (issue 06: ``[SSL: INVALID_SESSION_ID]``
    observado no survey) — rede caiu, próxima tentativa tem sucesso.
    """
    client = SenadoAdmClient(max_retries=3)
    payload = [{"sequencial": 1, "nome": "FULANO"}]

    with respx.mock:
        respx.get(_url("servidores/servidores")).mock(
            side_effect=[
                httpx.ConnectError("[SSL: INVALID_SESSION_ID]"),
                httpx.Response(200, json=payload),
            ]
        )
        result = await client.fetch("servidores/servidores")

    assert result == payload


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_senado_adm_client_raises_after_exhausted_retries(mock_sleep):
    """
    Se a API responde 429 em todas as tentativas, o cliente lança
    ``SenadoAdmAPIError`` após esgotar ``max_retries``.
    """
    client = SenadoAdmClient(max_retries=2)

    with respx.mock:
        respx.get(_url("servidores/servidores")).respond(429)

        with pytest.raises(SenadoAdmAPIError):
            await client.fetch("servidores/servidores")


@pytest.mark.asyncio
async def test_senado_adm_client_concurrency_bounded_by_semaphore():
    """
    Nenhuma requisição fora do semáforo: com 8 chamadas concorrentes e semáforo 2,
    o pico de requisições simultâneas nunca excede 2.
    """
    client = SenadoAdmClient()
    client._semaphore = asyncio.Semaphore(2)

    active = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.05)
        active -= 1
        return httpx.Response(200, json=[{"ok": True}])

    with respx.mock:
        respx.get(_url("servidores/servidores")).mock(side_effect=handler)
        await asyncio.gather(*[client.fetch("servidores/servidores") for _ in range(8)])

    assert peak <= 2


def test_senado_adm_client_exposes_base_url():
    """
    ``BASE_URL`` aponta para a API adm-dadosabertos — base que os extratores
    dos domínios (issues 07-09) usam para montar o ``_source_url``; o mecanismo
    único de auditoria (runner é autoridade) permanece intacto.
    """
    assert SENADO_ADM_API_BASE_URL == "https://adm.senado.gov.br/adm-dadosabertos/api/v1"
    assert SenadoAdmClient.BASE_URL == SENADO_ADM_API_BASE_URL
