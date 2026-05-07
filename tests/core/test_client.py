from unittest.mock import patch
from urllib.error import HTTPError

import httpx
import pytest
import respx
from ipolitico.core.client import CamaraAPIError, CamaraClient


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
    "ipolitico.core.client.asyncio.sleep"
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

    with respx.mock, patch("ipolitico.core.client.asyncio.sleep"):
        # O governo caiu de vez
        respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados").respond(status_code=500)

        # O sistema DEVE estourar esse erro específico para o orquestrador capturar
        with pytest.raises(CamaraAPIError, match="Falha catastrófica"):
            await client.fetch("deputados")


@pytest.mark.asyncio
@patch("ipolitico.core.client.asyncio.sleep")
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
@patch("ipolitico.core.client.urllib.request.urlopen")
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
@patch("ipolitico.core.client.asyncio.sleep")
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
