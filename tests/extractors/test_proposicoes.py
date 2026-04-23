import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.core.config import CAMARA_API_BASE_URL
from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.proposicoes import ProposicoesExtractor


class MockStateStore:
    def get_watermark(self, table: str, column: str) -> str | None:
        return "2023-01-01"

    def get_existing_ids(self, table: str, column: str = "id") -> list[int]:
        return []


@pytest.mark.asyncio
async def test_extract_proposicoes_success():
    client = CamaraClient()
    state_store = MockStateStore()
    extractor = ProposicoesExtractor(client, state_store)

    fake_payload = [
        {
            "id": 12345,
            "siglaTipo": "PL",
            "ano": 2023,
            "ementa": "Teste de PL",
            "dataApresentacao": "2023-05-10T14:00:00",
        }
    ]

    with respx.mock:
        route = respx.get(url__regex=rf".*{CAMARA_API_BASE_URL}{ApiRoutes.PROPOSICOES}.*").respond(
            status_code=200, json={"dados": fake_payload}
        )

        df = await extractor.extract(data_inicio="2023-01-01", data_fim="2023-12-31")

        assert route.called
        assert not df.is_empty()
        assert "id" in df.columns
        assert df["siglaTipo"][0] == "PL"
