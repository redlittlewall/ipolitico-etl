import logging
from unittest.mock import patch
from urllib.error import HTTPError

import httpx
import pytest
import respx

from ipolitico.core.camara_client import CamaraAPIError, CamaraClient
from ipolitico.core.exceptions import ResourceQuarantinedError


@pytest.mark.asyncio
async def test_camara_client_returns_empty_on_404():
    """
    Testa a defesa contra Falsos Positivos (ex: votações simbólicas).
    A API retorna HTTP 404, e o cliente deve interceptar e converter
    silenciosamente para uma lista vazia [], em vez de fazer retries inúteis.
    """
    client = CamaraClient()

    with respx.mock:
        respx.get("https://dadosabertos.camara.leg.br/api/v2/votacoes/123/votos").respond(
            status_code=404
        )

        resultado = await client.fetch("votacoes/123/votos")

        assert isinstance(resultado, list)
        assert len(resultado) == 0


@pytest.mark.asyncio
async def test_camara_client_empty_array_200():
    """
    Testa se o cliente lida corretamente com HTTP 200 e array vazio
    (ex: deputado sem gastos num determinado mês).
    """
    client = CamaraClient()

    with respx.mock:
        respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados/1/despesas").respond(
            status_code=200, json={"dados": [], "links": []}
        )

        resultado = await client.fetch("deputados/1/despesas")
        assert resultado == []


@pytest.mark.asyncio
async def test_camara_client_success():
    """
    Testa o caminho feliz: a API retorna dados estruturados e o cliente
    isola a chave 'dados' ignorando o resto.
    """
    client = CamaraClient()
    fake_payload = {"dados": [{"id": 1, "nome": "Deputado Teste"}], "links": [{"rel": "next"}]}

    with respx.mock:
        respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados").respond(
            status_code=200, json=fake_payload
        )

        resultado = await client.fetch("deputados")

        assert len(resultado) == 1
        assert resultado[0]["nome"] == "Deputado Teste"


@pytest.mark.asyncio
@patch(
    "ipolitico.core.camara_client.asyncio.sleep"
)  # Mockamos o sleep para o teste não demorar de verdade
async def test_camara_client_retry_and_backoff(mock_sleep):
    """
    Garante que o cliente respeita o Throttling (429) ou queda (503),
    espera o tempo correto (Exponential Backoff) e tenta de novo até ter sucesso.
    """
    client = CamaraClient(max_retries=3)

    with respx.mock:
        # Simulamos a API falhando 2 vezes seguidas e acertando na 3ª
        route = respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados")
        route.side_effect = [
            httpx.Response(429),  # Too Many Requests
            httpx.Response(503),  # Service Unavailable
            httpx.Response(200, json={"dados": [{"id": 1}], "links": []}),  # Sucesso
        ]

        resultado = await client.fetch("deputados")

        # Verifica se chegou no resultado após sofrer nas duas primeiras tentativas
        assert len(resultado) == 1
        # Verifica se a rota foi chamada exatamente 3 vezes
        assert route.call_count == 3
        # Verifica se acionou o 'recuo tático' (sleep) 2 vezes
        assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_camara_client_exhausted_retries():
    """Garante que a exceção CamaraAPIError é levantada se a API não voltar (Fail Fast)."""
    client = CamaraClient(max_retries=2)

    with respx.mock, patch("ipolitico.core.camara_client.asyncio.sleep"):
        # O governo caiu de vez
        respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados").respond(status_code=500)

        # O sistema DEVE estourar esse erro específico para o orquestrador capturar
        with pytest.raises(CamaraAPIError, match="Falha catastrófica"):
            await client.fetch("deputados")


@pytest.mark.asyncio
@patch("ipolitico.core.camara_client.asyncio.sleep")
async def test_camara_client_fetch_network_error(mock_sleep):
    """
    Garante que falhas FÍSICAS de rede (DNS, Timeout, Drop)
    acionam o backoff e levantam o erro catastrófico corretamente.
    """
    client = CamaraClient(max_retries=2)
    with respx.mock:
        route = respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados")
        # Simulamos um erro físico de rede, não um erro HTTP!
        route.side_effect = httpx.ConnectError("O servidor do governo sumiu do mapa")

        with pytest.raises(CamaraAPIError, match="Falha catastrófica"):
            await client.fetch("deputados")

        # Garante que tentou 2 vezes e esperou (backoff) nas duas
        assert route.call_count == 2
        assert mock_sleep.call_count == 2


@pytest.mark.asyncio
@patch("ipolitico.core.camara_client.urllib.request.urlopen")
async def test_camara_client_download_file(mock_urlopen, tmp_path):
    client = CamaraClient(max_retries=1)
    dest_path = tmp_path / "dump_teste.csv"

    # Simula um erro 404 do urllib
    mock_urlopen.side_effect = HTTPError(
        url="http://fake", code=404, msg="Not Found", hdrs={}, fp=None
    )

    sucesso_404 = await client.download_file("http://fake", str(dest_path))
    assert sucesso_404 is False


@pytest.mark.asyncio
async def test_camara_client_close_method():
    """
    Apenas para garantir a cobertura da linha 141 (método pass).
    Mantém o contrato arquitetural intacto.
    """
    client = CamaraClient()
    await client.close()


@pytest.mark.asyncio
@patch("ipolitico.core.camara_client.asyncio.sleep")
async def test_camara_client_network_error_recovered_logs_debug(mock_sleep, caplog):
    """
    Erro de rede transitório que se recupera nas retentativas é DEBUG, não ERROR.

    Eram ~158 linhas de ERROR por tentativa-que-recobra no run, poluindo o log
    sem falha real (a falha final já é surfada pelo runner com "Erro fatal").
    A mensagem inclui o tipo da exceção (ex: ConnectError) para diagnóstico —
    no run, a maioria aparecia com a mensagem vazia, impossibilitando saber
    que tipo de falha era.
    """
    caplog.set_level(logging.DEBUG, logger="ipolitico.core.camara_client")
    client = CamaraClient(max_retries=3)

    with respx.mock:
        route = respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados")
        route.side_effect = [
            httpx.ConnectError("O servidor do governo sumiu do mapa"),
            httpx.Response(200, json={"dados": [{"id": 1}], "links": []}),
        ]

        resultado = await client.fetch("deputados")

    assert len(resultado) == 1
    assert route.call_count == 2

    network_debug = [
        r for r in caplog.records if r.levelname == "DEBUG" and "Erro de rede" in r.getMessage()
    ]
    assert len(network_debug) == 1
    assert "ConnectError" in network_debug[0].getMessage()
    assert not any(r.levelname == "ERROR" for r in caplog.records)


@pytest.mark.asyncio
@patch("ipolitico.core.camara_client.asyncio.sleep")
async def test_camara_client_explicit_request_error(mock_sleep):
    """
    Força a cobertura exata da linha 'except httpx.RequestError'.
    Muitas vezes exceptions mais específicas (como ConnectError) burlam
    o tracking de cobertura da classe base.
    """
    client = CamaraClient(max_retries=1)

    with respx.mock:
        route = respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados")
        # Injeta diretamente o erro base do HTTPX
        route.side_effect = httpx.RequestError(
            "Erro base do HTTPX",
            request=httpx.Request("GET", "https://dadosabertos.camara.leg.br/api/v2/deputados"),
        )

        with pytest.raises(CamaraAPIError):
            await client.fetch("deputados")


# ── Quarentena de recursos 5xx + teto de backoff ──────────────────────────────

BASE = "https://dadosabertos.camara.leg.br/api/v2"


@pytest.mark.asyncio
@patch("ipolitico.core.camara_client.asyncio.sleep")
async def test_camara_client_backoff_capped(mock_sleep):
    """O backoff exponencial nunca dorme acima de ``max_backoff_s``.

    Sem o teto, a tentativa 10 dormiria 1024s (~17min). Com teto 30s, todos os
    sleeps ficam ≤ 30 — incluindo as tentativas altas.
    """
    client = CamaraClient(max_retries=10, max_backoff_s=30, quarantine_threshold=999)

    with respx.mock:
        respx.get(f"{BASE}/deputados").respond(status_code=500)

        # threshold 999 nunca tripa; max_retries 10 esgota → CamaraAPIError
        with pytest.raises(CamaraAPIError, match="Falha catastrófica"):
            await client.fetch("deputados")

    sleeps = [c.args[0] for c in mock_sleep.call_args_list]
    assert len(sleeps) == 10  # uma espera por tentativa
    assert max(sleeps) <= 30
    assert all(s >= 1 for s in sleeps)


@pytest.mark.asyncio
@patch("ipolitico.core.camara_client.asyncio.sleep")
async def test_camara_client_quarantine_after_threshold(mock_sleep):
    """Após ``quarantine_threshold`` falhas 5xx seguidas, o recurso é posto em
    quarentena: o erro é levantado e chamadas seguintes ao mesmo recurso sobem
    imediatamente, sem contato com a rede.
    """
    client = CamaraClient(max_retries=10, max_backoff_s=30, quarantine_threshold=3)

    with respx.mock:
        route = respx.get(f"{BASE}/deputados/1/discursos").respond(status_code=500)

        with pytest.raises(ResourceQuarantinedError):
            await client.fetch("deputados/1/discursos")
        assert route.call_count == 3  # tripa na 3ª, sem pagar o backoff da 3ª

        with pytest.raises(ResourceQuarantinedError):
            await client.fetch("deputados/1/discursos")
        assert route.call_count == 3  # nenhuma chamada HTTP extra


@pytest.mark.asyncio
@patch("ipolitico.core.camara_client.asyncio.sleep")
async def test_camara_client_quarantine_resets_on_success(mock_sleep):
    """Um sucesso (2xx) zera o contador de falhas consecutivas do recurso."""
    client = CamaraClient(max_retries=10, max_backoff_s=30, quarantine_threshold=3)

    with respx.mock:
        route = respx.get(f"{BASE}/deputados/1/discursos")
        # 500, 500, 200 → contador reseta no sucesso
        route.side_effect = [
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(200, json={"dados": [], "links": []}),
        ]
        await client.fetch("deputados/1/discursos")

        # Depois, 500 × 3 consecutivos → agora sim a quarentena tripa
        route.side_effect = None
        route.respond(status_code=500)
        with pytest.raises(ResourceQuarantinedError):
            await client.fetch("deputados/1/discursos")

        assert route.call_count == 6  # 3 (primeira série) + 3 (segunda série)


@pytest.mark.asyncio
@patch("ipolitico.core.camara_client.asyncio.sleep")
async def test_camara_client_quarantine_keyed_by_stable_params(mock_sleep):
    """Recursos com params estáveis distintos são chaves independentes.

    Um mês podre em ``despesas?ano=2024&mes=3`` não quarentena o mês seguinte.
    """
    client = CamaraClient(max_retries=4, max_backoff_s=30, quarantine_threshold=3)

    with respx.mock:
        route_mar = respx.get(
            f"{BASE}/deputados/1/despesas",
            params={"ano": "2024", "mes": "3"},
        ).respond(status_code=500)
        route_abr = respx.get(
            f"{BASE}/deputados/1/despesas",
            params={"ano": "2024", "mes": "4"},
        ).respond(status_code=500)

        # março tripa a quarentena
        with pytest.raises(ResourceQuarantinedError):
            await client.fetch("deputados/1/despesas", params={"ano": "2024", "mes": "3"})
        assert route_mar.call_count == 3

        # abril NÃO é contaminado pela chave de março: retenta por conta própria
        # (abril também responde 500 — é outra maçã podre — e tripa a SUA
        # quarentena). O que importa: nenhuma chamada é pulada via chave alheia.
        with pytest.raises(ResourceQuarantinedError):
            await client.fetch("deputados/1/despesas", params={"ano": "2024", "mes": "4"})
        assert route_abr.call_count == 3  # contador próprio, não pulado por março
        assert len(client._quarantined) == 2  # duas chaves independentes


@pytest.mark.asyncio
@patch("ipolitico.core.camara_client.asyncio.sleep")
async def test_camara_client_quarantine_ignores_pagination_params(mock_sleep):
    """Params de paginação não participam da chave de quarentena.

    Páginas da MESMA janela compartilham o contador: após a quarentena na
    página 1, a página 2 é pulada sem chamada HTTP.
    """
    client = CamaraClient(max_retries=4, max_backoff_s=30, quarantine_threshold=3)

    with respx.mock:
        route_p1 = respx.get(
            f"{BASE}/deputados/1/discursos",
            params={"dataInicio": "2015-02-01", "dataFim": "2019-01-31", "pagina": 1},
        ).respond(status_code=500)
        route_p2 = respx.get(
            f"{BASE}/deputados/1/discursos",
            params={"dataInicio": "2015-02-01", "dataFim": "2019-01-31", "pagina": 2},
        ).respond(status_code=500)

        with pytest.raises(ResourceQuarantinedError):
            await client.fetch(
                "deputados/1/discursos",
                params={"dataInicio": "2015-02-01", "dataFim": "2019-01-31", "pagina": 1},
            )
        assert route_p1.call_count == 3

        # mesma janela, outra página → mesma chave → sobe imediato, rede intocada
        with pytest.raises(ResourceQuarantinedError):
            await client.fetch(
                "deputados/1/discursos",
                params={"dataInicio": "2015-02-01", "dataFim": "2019-01-31", "pagina": 2},
            )
        assert route_p2.call_count == 0


@pytest.mark.asyncio
@patch("ipolitico.core.camara_client.asyncio.sleep")
async def test_camara_client_quarantine_ignores_429(mock_sleep):
    """HTTP 429 NÃO entra em quarentena: é rate-limit global, não recurso podre."""
    client = CamaraClient(max_retries=4, max_backoff_s=30, quarantine_threshold=3)

    with respx.mock:
        route = respx.get(f"{BASE}/deputados").respond(status_code=429)

        # 4 × 429 esgota max_retries → CamaraAPIError, NUNCA ResourceQuarantinedError
        with pytest.raises(CamaraAPIError, match="Falha catastrófica"):
            await client.fetch("deputados")
        assert route.call_count == 4

        # contador intacto: uma nova chamada volta a retentar do zero
        with pytest.raises(CamaraAPIError, match="Falha catastrófica"):
            await client.fetch("deputados")
        assert route.call_count == 8


@pytest.mark.asyncio
@patch("ipolitico.core.camara_client.asyncio.sleep")
async def test_camara_client_quarantine_ignores_transport_errors(mock_sleep):
    """Erros de transporte (rede/DNS) não incrementam o contador de quarentena."""
    client = CamaraClient(max_retries=4, max_backoff_s=30, quarantine_threshold=3)

    with respx.mock:
        route = respx.get(f"{BASE}/deputados")
        route.side_effect = httpx.ConnectError("fora do ar")

        with pytest.raises(CamaraAPIError, match="Falha catastrófica"):
            await client.fetch("deputados")
        assert route.call_count == 4
        assert client._quarantined == set()  # transporte não conta

        # 500 × 3 agora tripa exatamente em 3 — provando que o transporte não
        # incrementou o contador
        route.side_effect = None
        route.respond(status_code=500)
        with pytest.raises(ResourceQuarantinedError):
            await client.fetch("deputados")
        assert route.call_count == 4 + 3
