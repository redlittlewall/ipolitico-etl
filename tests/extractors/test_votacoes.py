from unittest.mock import MagicMock

import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.extractors.votacoes import VotacoesExtractor


@pytest.mark.asyncio
async def test_votacoes_extractor_inheritance():
    client = CamaraClient()
    extractor = VotacoesExtractor(client, db_path="fake.db")

    # Mockando o método da classe PAI
    extractor._get_last_watermark = MagicMock(return_value="2024-01-01")

    with respx.mock:
        route = respx.get(url__contains="dataInicio=2024-01-01").respond(
            status_code=200, json={"dados": []}
        )
        await extractor.extract()
        assert route.called
