from unittest.mock import MagicMock

import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.extractors.camara.votacoes import VotacoesExtractor


@pytest.mark.asyncio
async def test_votacoes_extractor_inheritance():
    client = CamaraClient()
    extractor = VotacoesExtractor(client, db_path="fake.db")

    data_teste = "2024-01-01"
    extractor._get_last_watermark = MagicMock(return_value=data_teste)

    with respx.mock:
        mock_data = [{"id": "999", "dataHoraRegistro": "2024-01-01T10:00:00"}]
        route = respx.get(url__regex=rf".*votacoes.*dataInicio={data_teste}.*").respond(
            status_code=200, json={"dados": mock_data}
        )

        df = await extractor.extract()

        assert route.called
        assert df["id"][0] == "999"
