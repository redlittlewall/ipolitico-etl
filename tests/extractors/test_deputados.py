import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.core.config import CAMARA_API_BASE_URL
from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.deputados import DeputadosExtractor


# "Dublê" do State Store para isolar o teste do banco de dados
class MockStateStore:
    def get_watermark(self, table: str, column: str) -> str | None:
        return None

    def get_existing_ids(self, table: str, column: str = "id") -> list[int]:
        return []


@pytest.mark.asyncio
async def test_extract_deputados_especificos():
    client = CamaraClient()
    state_store = MockStateStore()
    extractor = DeputadosExtractor(client, state_store)

    fake_payload = [
        {"id": 123, "nome": "Deputado Teste", "siglaPartido": "PT"},
        {"id": 456, "nome": "Deputado Teste 2", "siglaPartido": "PL"},
    ]

    with respx.mock:
        # Mockamos a rota de deputados
        route_deputados = respx.get(url__regex=rf".*{ApiRoutes.DEPUTADOS}.*").respond(
            status_code=200, json={"dados": fake_payload}
        )

        # Testamos a extração passando uma legislatura específica
        df = await extractor.extract(legislatura=57)

        assert route_deputados.called
        assert not df.is_empty()
        assert df.height == 2
        assert "nome" in df.columns


@pytest.mark.asyncio
async def test_extract_detalhes_deputados():
    client = CamaraClient()
    state_store = MockStateStore()
    extractor = DeputadosExtractor(client, state_store)

    deputado_id = 123
    fake_detalhe = {"id": deputado_id, "nomeCivil": "Nome Completo", "cpf": "000.000.000-00"}

    with respx.mock:
        # Mockamos a rota de detalhes de UM deputado específico
        route_detalhes = respx.get(
            f"{CAMARA_API_BASE_URL}{ApiRoutes.DEPUTADOS}/{deputado_id}"
        ).respond(status_code=200, json={"dados": fake_detalhe})

        df = await extractor.extract_detalhes([deputado_id])

        assert route_detalhes.called
        assert not df.is_empty()
        assert df["nomeCivil"][0] == "Nome Completo"
