import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.core.config import CAMARA_API_BASE_URL
from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.votacoes import VotacoesExtractor


class MockStateStore:
    def get_watermark(self, table: str, column: str) -> str | None:
        return "2023-01-01"

    def get_existing_ids(self, table: str, column: str = "id") -> list[int]:
        return []


@pytest.mark.asyncio
async def test_extract_votacoes_success():
    client = CamaraClient()
    state_store = MockStateStore()
    extractor = VotacoesExtractor(client, state_store)

    fake_payload = [
        {"id": "98765-4321", "uri": "https...", "data": "2023-08-15", "siglaOrgao": "PLEN"}
    ]

    with respx.mock:
        route = respx.get(url__regex=rf".*{CAMARA_API_BASE_URL}{ApiRoutes.VOTACOES}.*").respond(
            status_code=200, json={"dados": fake_payload}
        )

        df = await extractor.extract(data_inicio="2023-08-01", data_fim="2023-08-31")

        assert route.called
        assert not df.is_empty()
        assert "id" in df.columns
        assert df["data"][0] == "2023-08-15"
