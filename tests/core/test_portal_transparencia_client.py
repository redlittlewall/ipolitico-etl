"""Testes do PortalTransparenciaClient — comportamento público, não implementação.

Prior art: ``tests/core/test_senado_adm_client.py`` — client mockado via ``respx``.
O cliente da API v3 do Portal da Transparência (CGU) segue o mesmo padrão:
semáforo próprio, retry tenacity só para erros transitórios, 404 → lista vazia.
A diferença é a autenticação por chave do usuário (header ``chave-api-dados``)
e o ``download_file`` com resume via Range header (dumps bulk de /download-de-dados).
"""

import asyncio
from unittest.mock import patch

import httpx
import pytest
import respx

from ipolitico.core.config import PORTAL_API_BASE_URL
from ipolitico.core.portal_transparencia_client import (
    PortalTransparenciaAPIError,
    PortalTransparenciaAuthError,
    PortalTransparenciaClient,
)

# Chave de teste — NUNCA uma chave real (a real vive só no .env, gitignored).
API_KEY = "chave-de-teste-fake"
# URL de dump bulk no padrão real do portal: /download-de-dados/{módulo}/{YYYYMM}
# (302 → dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/...).
BULK_URL = "https://portaldatransparencia.gov.br/download-de-dados/servidores/202401"


def _url(endpoint: str) -> str:
    """Monta a URL completa da API v3 para as rotas respx."""
    return f"{PORTAL_API_BASE_URL}/{endpoint.lstrip('/')}"


# ── fetch: API v3 ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_portal_client_returns_top_level_list():
    """
    Shape agnóstico: a API v3 devolve lista top-level (ex: /api-de-dados/orgaos-siape)
    — o cliente entrega o JSON como veio, sem normalizar envelope.
    """
    client = PortalTransparenciaClient(api_key=API_KEY)
    payload = [{"codigo": 1, "descricao": "CASA CIVIL"}]

    with respx.mock:
        respx.get(_url("api-de-dados/orgaos-siape")).respond(200, json=payload)
        result = await client.fetch("api-de-dados/orgaos-siape", params={"pagina": 1})

    assert result == payload


@pytest.mark.asyncio
async def test_portal_client_sends_auth_header():
    """
    Autenticação por chave do usuário: a chave vai no header ``chave-api-dados``
    (contracto da API v3 — sem ela, HTTP 401).
    """
    client = PortalTransparenciaClient(api_key=API_KEY)

    with respx.mock:
        route = respx.get(_url("api-de-dados/orgaos-siape")).respond(200, json=[])
        await client.fetch("api-de-dados/orgaos-siape")

    assert route.calls[0].request.headers["chave-api-dados"] == API_KEY


@pytest.mark.asyncio
async def test_portal_client_404_returns_empty_list():
    """
    404 = ausência (recurso sem dados), não exceção: lista vazia, sem retry
    (mesmo padrão do CamaraClient/SenadoAdmClient).
    """
    client = PortalTransparenciaClient(api_key=API_KEY)

    with respx.mock:
        route = respx.get(_url("api-de-dados/orgaos-siape")).respond(404)
        result = await client.fetch("api-de-dados/orgaos-siape")

    assert isinstance(result, list)
    assert result == []
    assert route.call_count == 1  # sem retry em 404


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_portal_client_retries_on_429_then_success(mock_sleep):
    """Retry cobre HTTP 429 (throttling): sucesso na segunda tentativa."""
    client = PortalTransparenciaClient(api_key=API_KEY, max_retries=3)
    payload = [{"codigo": 1, "descricao": "CASA CIVIL"}]

    with respx.mock:
        respx.get(_url("api-de-dados/orgaos-siape")).mock(
            side_effect=[httpx.Response(429), httpx.Response(200, json=payload)]
        )
        result = await client.fetch("api-de-dados/orgaos-siape")

    assert result == payload


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_portal_client_retries_on_5xx_then_success(mock_sleep):
    """Retry cobre HTTP 5xx (ex: 503 da API): sucesso na segunda tentativa."""
    client = PortalTransparenciaClient(api_key=API_KEY, max_retries=3)
    payload = [{"codigo": 1, "descricao": "CASA CIVIL"}]

    with respx.mock:
        respx.get(_url("api-de-dados/orgaos-siape")).mock(
            side_effect=[httpx.Response(503), httpx.Response(200, json=payload)]
        )
        result = await client.fetch("api-de-dados/orgaos-siape")

    assert result == payload


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_portal_client_retries_on_network_error_then_success(mock_sleep):
    """
    Retry cobre erro de rede transiente (ex: conexão caiu) — próxima tentativa
    tem sucesso.
    """
    client = PortalTransparenciaClient(api_key=API_KEY, max_retries=3)
    payload = [{"codigo": 1, "descricao": "CASA CIVIL"}]

    with respx.mock:
        respx.get(_url("api-de-dados/orgaos-siape")).mock(
            side_effect=[
                httpx.ConnectError("connection refused"),
                httpx.Response(200, json=payload),
            ]
        )
        result = await client.fetch("api-de-dados/orgaos-siape")

    assert result == payload


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_portal_client_does_not_retry_fatal_http_error(mock_sleep):
    """
    Erro HTTP fatal (demais 4xx, ex: 400) não é transitório: sem retry, levanta
    ``PortalTransparenciaAPIError`` na primeira tentativa.
    """
    client = PortalTransparenciaClient(api_key=API_KEY, max_retries=3)

    with respx.mock:
        route = respx.get(_url("api-de-dados/orgaos-siape")).respond(400)

        with pytest.raises(PortalTransparenciaAPIError):
            await client.fetch("api-de-dados/orgaos-siape")

    assert route.call_count == 1  # sem retry em erro fatal


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_portal_client_raises_auth_error_on_401(mock_sleep):
    """
    401 = chave inválida ou ausente: erro de autenticação distinto, sem retry
    (re-tentar com a mesma chave não muda nada).
    """
    client = PortalTransparenciaClient(api_key=API_KEY, max_retries=3)

    with respx.mock:
        route = respx.get(_url("api-de-dados/orgaos-siape")).respond(401)

        with pytest.raises(PortalTransparenciaAuthError):
            await client.fetch("api-de-dados/orgaos-siape")

    assert route.call_count == 1  # sem retry em 401


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_portal_client_raises_after_exhausted_retries(mock_sleep):
    """Se a API responde 429 em todas as tentativas, o cliente levanta erro."""
    client = PortalTransparenciaClient(api_key=API_KEY, max_retries=2)

    with respx.mock:
        respx.get(_url("api-de-dados/orgaos-siape")).respond(429)

        with pytest.raises(PortalTransparenciaAPIError):
            await client.fetch("api-de-dados/orgaos-siape")


@pytest.mark.asyncio
async def test_portal_client_concurrency_bounded_by_semaphore():
    """
    Nenhuma requisição fora do semáforo: com 8 chamadas concorrentes e semáforo 2,
    o pico de requisições simultâneas nunca excede 2.
    """
    client = PortalTransparenciaClient(api_key=API_KEY)
    client._semaphore = asyncio.Semaphore(2)

    active = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.05)
        active -= 1
        return httpx.Response(200, json=[{"codigo": 1, "descricao": "X"}])

    with respx.mock:
        respx.get(_url("api-de-dados/orgaos-siape")).mock(side_effect=handler)
        await asyncio.gather(*[client.fetch("api-de-dados/orgaos-siape") for _ in range(8)])

    assert peak <= 2


def test_portal_client_exposes_base_url():
    """``BASE_URL`` aponta para a API v3 — base que os extratores usam na auditoria."""
    assert PORTAL_API_BASE_URL == "https://api.portaldatransparencia.gov.br"
    assert PortalTransparenciaClient.BASE_URL == PORTAL_API_BASE_URL


# ── download_file: dumps bulk com resume via Range header ─────────────────────


@pytest.mark.asyncio
async def test_download_file_writes_full_file(tmp_path):
    """Download completo (200): arquivo escrito do zero, sem Range."""
    client = PortalTransparenciaClient(api_key=API_KEY)
    dest = tmp_path / "202401.zip"

    with respx.mock:
        route = respx.get(BULK_URL).respond(200, content=b"dados-brutos")
        ok = await client.download_file(BULK_URL, str(dest))

    assert ok is True
    assert dest.read_bytes() == b"dados-brutos"
    assert route.calls[0].request.headers.get("range") is None


@pytest.mark.asyncio
async def test_download_file_404_returns_false(tmp_path):
    """
    404 = arquivo não publicado (ausência), não exceção: ``False`` para o extrator
    devolver lista vazia.
    """
    client = PortalTransparenciaClient(api_key=API_KEY)
    dest = tmp_path / "202401.zip"

    with respx.mock:
        route = respx.get(BULK_URL).respond(404)
        ok = await client.download_file(BULK_URL, str(dest))

    assert ok is False
    assert not dest.exists()
    assert route.call_count == 1  # sem retry em 404


@pytest.mark.asyncio
async def test_download_file_416_returns_true(tmp_path):
    """
    416 Range Not Satisfiable = o arquivo local já está completo (resume idempotente):
    retorna ``True`` sem reescrever nada.
    """
    client = PortalTransparenciaClient(api_key=API_KEY)
    dest = tmp_path / "202401.zip"
    dest.write_bytes(b"completo")

    with respx.mock:
        respx.get(BULK_URL).respond(416)
        ok = await client.download_file(BULK_URL, str(dest))

    assert ok is True
    assert dest.read_bytes() == b"completo"  # intocado


@pytest.mark.asyncio
async def test_download_file_resumes_partial_with_range_header(tmp_path):
    """
    Resume via Range header: arquivo parcial existente → o cliente pede
    ``Range: bytes=N-`` e anexa a resposta 206 ao que já existe.
    """
    client = PortalTransparenciaClient(api_key=API_KEY)
    dest = tmp_path / "202401.zip"
    dest.write_bytes(b"primeir")  # 7 bytes já baixados

    with respx.mock:
        route = respx.get(BULK_URL).mock(
            side_effect=lambda request: httpx.Response(
                206,
                content=b"a-parte",
                headers={"content-range": "bytes 7-13/14"},
            )
        )
        ok = await client.download_file(BULK_URL, str(dest))

    assert ok is True
    assert route.calls[0].request.headers["range"] == "bytes=7-"
    assert dest.read_bytes() == b"primeir" + b"a-parte"


@pytest.mark.asyncio
@patch("asyncio.sleep")
async def test_download_file_resumes_after_mid_stream_drop(mock_sleep, tmp_path):
    """
    Queda no meio do download → retry com Range maior (resume do byte parcial),
    sem recomeçar do zero: é a defesa contra o WAF derrubando conexões longas.
    """
    client = PortalTransparenciaClient(max_retries=3)
    dest = tmp_path / "202401.zip"
    calls: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers.get("range"))
        if len(calls) == 1:
            # Simula: o servidor entregou 3 bytes e a conexão caiu no meio.
            dest.write_bytes(b"abc")
            raise httpx.ReadError("connection reset mid-stream")
        assert request.headers.get("range") == "bytes=3-"
        return httpx.Response(206, content=b"def", headers={"content-range": "bytes 3-5/6"})

    with respx.mock:
        respx.get(BULK_URL).mock(side_effect=handler)
        ok = await client.download_file(BULK_URL, str(dest))

    assert ok is True
    assert dest.read_bytes() == b"abcdef"
    assert calls == [None, "bytes=3-"]
