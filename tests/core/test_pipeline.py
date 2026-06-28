"""Testes alinhados ao PipelineManager (suíte legada SQLite/run_pipeline removida)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ipolitico.core.constants import DomainType, LoadStrategy, SinkType
from ipolitico.pipeline.manager import PipelineManager


@pytest.mark.asyncio
async def test_run_domain_short_circuits_without_yaml_config():
    builder = MagicMock()
    runner = MagicMock()
    runner.execute = AsyncMock()
    config = {"domain_configs": {}}
    store = MagicMock()

    mgr = PipelineManager(builder, runner, config, store)
    await mgr.run_domain(
        DomainType.DEPUTADOS,
        SinkType.DATALAKE,
        LoadStrategy.INCREMENTAL,
    )

    builder.build.assert_not_called()
    runner.execute.assert_not_awaited()
