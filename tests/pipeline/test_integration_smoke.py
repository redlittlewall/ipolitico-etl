"""Smoke de integração: manager + mocks, sem rede."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import polars as pl
import pytest
from ipolitico.core.constants import DomainType, LoadStrategy, MedallionLayer, SinkType
from ipolitico.pipeline.builder import PipelineBuilder, PipelineComponents
from ipolitico.pipeline.manager import PipelineManager
from ipolitico.pipeline.runner import PipelineRunner
from ipolitico.sinks.datalake_sink import DataLakeSink
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
    mock_sink.flush = AsyncMock()
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


@pytest.mark.asyncio
async def test_pipeline_runner_consolidates_with_real_datalake_sink():
    """
    Teste de integração: PipelineRunner real + DataLakeSink real.

    Simula workers paralelos produzindo N chunks pequenos.
    Verifica que o buffer + flush consolidam em 1 arquivo final,
    e que captured_at está presente nos dados persistidos.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        sink = DataLakeSink(base_dir=tmpdir, flush_size_mb=0, flush_interval_s=0)
        runner = PipelineRunner(max_workers=3)

        # Extractor mockado que retorna 1 registro por chamada (async)
        extractor = MagicMock()
        extractor.extract = AsyncMock()
        extractor.extract.side_effect = [
            pl.DataFrame({"id": [i], "nome": [f"Item-{i}"]}) for i in range(10)
        ]

        # Transformer passthrough (só retorna o próprio raw_df)
        transformer = MagicMock()
        transformer.transform.side_effect = lambda raw_df, **kw: raw_df

        components = PipelineComponents(
            extractor=extractor,
            transformer=transformer,
            sink=sink,
        )

        items = list(range(10))

        def mapper(item: int):
            return {"item": item}

        await runner.execute(
            components=components,
            items=items,
            extract_kwargs_mapper=mapper,
            table_name="integracao",
            unique_keys=["id"],
            layer=MedallionLayer.SILVER,
        )

        # Verificação: 1 arquivo consolidado (não 10 micro-arquivos)
        layer_dir = Path(tmpdir) / MedallionLayer.SILVER.value / "integracao"
        files = sorted(layer_dir.glob("*.parquet"))
        assert len(files) == 1, f"Esperado 1 arquivo consolidado, obtido {len(files)}"

        # Conteúdo correto
        result = pl.read_parquet(files[0])
        assert result.height == 10
        assert sorted(result["id"].to_list()) == list(range(10))

        # captured_at presente
        assert "captured_at" in result.columns

        # flush foi chamado (garantia do runner)
        assert result["captured_at"].is_not_null().all()
