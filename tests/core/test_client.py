import pytest
import respx
from ipolitico.core.client import CamaraClient


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
