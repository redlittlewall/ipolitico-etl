import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.core.config import CAMARA_API_BASE_URL
from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.despesas import DespesasExtractor


class MockStateStore:
    def get_watermark(self, table: str, column: str) -> str | None:
        return "2024-01-01"

    def get_existing_ids(self, table: str, column: str = "id") -> list[int]:
        return []


@pytest.mark.asyncio
async def test_extract_despesas_success():
    client = CamaraClient()
    state_store = MockStateStore()
    extractor = DespesasExtractor(client, state_store)

    dep_id = 500

    fake_payload = [
        {"numDocumento": "123", "dataDocumento": "2024-01-10", "valorLiquido": 150.00},
    ]

    with respx.mock:
        route = respx.get(
            url__regex=rf".*{CAMARA_API_BASE_URL}{ApiRoutes.DEPUTADOS}/{dep_id}/despesas.*"
        ).respond(status_code=200, json={"dados": fake_payload})

        df = await extractor.extract([dep_id], data_inicio="2024-01-01", data_fim="2024-01-31")

        assert route.called
        assert not df.is_empty()
        assert "id_deputado" in df.columns
        assert df["dataDocumento"][0] == "2024-01-10"
