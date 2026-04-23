import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.extractors.despesas import DespesasExtractor


@pytest.mark.asyncio
async def test_extract_despesas_success():
    client = CamaraClient()
    extractor = DespesasExtractor(client, db_path="fake.db")
    dep_id = 500

    fake_payload = [
        {"numDocumento": "123", "dataEmissao": "2024-01-10", "valorLiquido": 150.00},
    ]

    with respx.mock:
        url = f"https://dadosabertos.camara.leg.br/api/v2/deputados/{dep_id}/despesas"
        respx.get(url).respond(status_code=200, json={"dados": fake_payload})

        df = await extractor.extract([dep_id])

        assert not df.is_empty()
        assert df["id_deputado"][0] == dep_id
        assert df["valorLiquido"][0] == 150.00
