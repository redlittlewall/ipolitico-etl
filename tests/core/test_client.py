import pytest
import respx
from ipolitico.core.client import CamaraClient, SilentEmptyDataError


@pytest.mark.asyncio
async def test_camara_client_silent_empty_data_error():
    """
    Testa a anomalia governamental mapeada:
    A API retorna HTTP 200, mas o payload 'dados' é um array vazio.
    O client deve interceptar isso e levantar um erro em vez de seguir com o ETL.
    """
    client = CamaraClient()

    # Usamos o respx para interceptar a chamada de rede e simular o erro do governo
    with respx.mock:
        respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados").respond(
            status_code=200, json={"dados": [], "links": []}
        )

        # O teste PASSARÁ se a função levantar a exceção SilentEmptyDataError
        with pytest.raises(SilentEmptyDataError):
            await client.fetch("deputados")


@pytest.mark.asyncio
async def test_camara_client_success():
    """
    Testa o caminho feliz: a API retorna dados estruturados.
    """
    client = CamaraClient()
    fake_payload = {"dados": [{"id": 1, "nome": "Deputado Teste"}], "links": []}

    with respx.mock:
        respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados").respond(
            status_code=200, json=fake_payload
        )

        resultado = await client.fetch("deputados")

        assert len(resultado) == 1
        assert resultado[0]["nome"] == "Deputado Teste"
