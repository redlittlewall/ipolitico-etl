from unittest.mock import MagicMock

import polars as pl
import pytest
import respx
from ipolitico.core.client import CamaraClient
from ipolitico.extractors.proposicoes import ProposicoesExtractor


@pytest.mark.asyncio
async def test_proposicoes_incremental_flow():
    client = CamaraClient()
    extractor = ProposicoesExtractor(client, db_path="fake.db")

    extractor._get_last_watermark = MagicMock(return_value="2023-12-25")

    with respx.mock:
        route = respx.get(url__contains="dataInicio=2023-12-25").respond(
            status_code=200, json={"dados": [{"id": 1, "ementa": "Teste"}]}
        )

        df = await extractor.extract()

        assert route.called
        assert isinstance(df, pl.DataFrame)
        assert df.height == 1
