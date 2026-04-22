import polars as pl
import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.extractors.deputados import DeputadosExtractor


@pytest.mark.asyncio
async def test_extract_deputados_success():
    """
    Valida a extração de deputados após refatoração para BaseExtractor.
    """
    client = CamaraClient()
    extractor = DeputadosExtractor(client, db_path="fake.db")

    fake_data = [{"id": 1, "nome": "Deputado Refatorado", "siglaPartido": "ABC"}]

    with respx.mock:
        respx.get("https://dadosabertos.camara.leg.br/api/v2/deputados").respond(
            status_code=200, json={"dados": fake_data}
        )

        df = await extractor.extract()

        assert isinstance(df, pl.DataFrame)
        assert df.height == 1
        assert df["nome"][0] == "Deputado Refatorado"
