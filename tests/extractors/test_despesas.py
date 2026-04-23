import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.extractors.despesas import DespesasExtractor


@pytest.mark.asyncio
async def test_extract_despesas_success():
    client = CamaraClient()
    extractor = DespesasExtractor(client, db_path="fake.db")
    dep_id = 500

    # Atualizado de dataEmissao para dataDocumento
    fake_payload = [
        {"numDocumento": "123", "dataDocumento": "2024-01-10", "valorLiquido": 150.00},
    ]

    with respx.mock:
        # Usamos regex porque agora a URL real contém ano, mes, pagina e itens
        route = respx.get(url__regex=rf".*deputados/{dep_id}/despesas.*").respond(
            status_code=200, json={"dados": fake_payload}
        )

        # Simulando uma busca com datas explícitas para garantir o teste
        df = await extractor.extract([dep_id], data_inicio="2024-01-01", data_fim="2024-01-31")

        assert route.called
        assert not df.is_empty()
        assert "id_deputado" in df.columns
        assert df["dataDocumento"][0] == "2024-01-10"
