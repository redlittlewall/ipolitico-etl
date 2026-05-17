"""Smoke de integração: manager + mocks, sem rede."""

from unittest.mock import AsyncMock, MagicMock, patch

import polars as pl
import pytest
from ipolitico.core.constants import DomainType, LoadStrategy, SinkType
from ipolitico.pipeline.builder import PipelineBuilder, PipelineComponents
from ipolitico.pipeline.manager import PipelineManager
from ipolitico.pipeline.runner import PipelineRunner
from ipolitico.transformers.camara.proposicoes_transformer import CamaraProposicoesTransformer


@pytest.mark.asyncio
async def test_manager_run_domain_proposicoes_mocked():
    client = MagicMock()
    builder = PipelineBuilder(client)
    runner = PipelineRunner(max_workers=1)
    state = MagicMock()
    state.get_watermark.return_value = None
    state.get_existing_ids.return_value = []

    config = {
        "domain_configs": {
            "proposicoes": {
                "extractor": "ipolitico.extractors.camara.api.proposicoes.ProposicoesExtractor",
                "transformer": (
                    "ipolitico.transformers.camara.proposicoes_transformer."
                    "CamaraProposicoesTransformer"
                ),
                "sinks": {"datalake": "ipolitico.sinks.datalake_sink.DataLakeSink"},
            }
        }
    }

    metadata = MagicMock()
    metadata.get_current_legislature_id = AsyncMock(return_value=57)
    metadata.get_legislature_start_date = AsyncMock(return_value="2023-02-01")

    manager = PipelineManager(builder, runner, config, state, metadata_service=metadata)

    sample = pl.DataFrame(
        {
            "id": [1],
            "uri": ["u"],
            "siglaTipo": ["PL"],
            "numero": [1],
            "ano": [2024],
            "ementa": ["teste"],
            "dataApresentacao": ["2024-03-15T00:00:00"],
            "uriOrgaoNumerador": [None],
        }
    )

    mock_extractor = MagicMock()
    mock_extractor.extract = AsyncMock(return_value=sample)
    mock_sink = MagicMock()
    mock_sink.save = AsyncMock()
    components = PipelineComponents(
        extractor=mock_extractor,
        transformer=CamaraProposicoesTransformer(),
        sink=mock_sink,
    )

    with patch.object(builder, "build", return_value=components):
        await manager.run_domain(
            DomainType.PROPOSICOES,
            SinkType.DATALAKE,
            LoadStrategy.INCREMENTAL,
            start_date="2024-03-01",
            end_date="2024-03-31",
        )

    mock_sink.save.assert_awaited()
