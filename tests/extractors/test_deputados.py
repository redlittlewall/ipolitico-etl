import httpx
import polars as pl
import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.extractors.deputados import DeputadosExtractor


@pytest.mark.asyncio
async def test_extract_deputados_atuais_success():
    """
    Testa se o extrator converte corretamente o JSON da API em um DataFrame Polars.
    """
    # Setup
    client = CamaraClient()
    extractor = DeputadosExtractor(client)

    fake_data = [
        {"id": 1, "nome": "Deputado A", "siglaPartido": "P1"},
        {"id": 2, "nome": "Deputado B", "siglaPartido": "P2"},
    ]

    # Mock da rota /deputados com o parâmetro idLegislatura=57
    with respx.mock:
        respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados").mock(
            return_value=httpx.Response(200, json={"dados": fake_data})
        )

        df = await extractor.extract_atuaies()

        # Validações
        assert isinstance(df, pl.DataFrame)
        assert df.height == 2
        assert df["nome"][0] == "Deputado A"
        assert "siglaPartido" in df.columns
