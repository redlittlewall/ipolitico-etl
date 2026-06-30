"""Testes: PipelineManager aceita StateStore (DataLakeRepository) como state_store."""

from pathlib import Path
from unittest.mock import MagicMock

from ipolitico.pipeline.builder import PipelineBuilder
from ipolitico.pipeline.manager import PipelineManager
from ipolitico.pipeline.runner import PipelineRunner
from ipolitico.storage.datalake_repository import DataLakeRepository
from ipolitico.storage.state_store import StateStore


class TestPipelineManagerWithStateStore:
    """PipelineManager aceita StateStore em vez de BaseSink como state_store."""

    def test_accepts_datalake_repository_as_state_store(self, tmp_path: Path):
        """DataLakeRepository (implementa StateStore) é aceito como state_store."""
        builder = MagicMock(spec=PipelineBuilder)
        runner = MagicMock(spec=PipelineRunner)
        config = {"domain_configs": {}}
        metadata = MagicMock()
        lake = DataLakeRepository(tmp_path)

        # Deve construir sem erro (não requer BaseSink)
        manager = PipelineManager(
            builder=builder,
            runner=runner,
            config=config,
            state_store=lake,
            metadata_service=metadata,
        )

        assert isinstance(manager, PipelineManager)
        # Verifica que o lake interno usa o mesmo diretório
        assert manager._lake is not None
        assert str(manager._lake.base_dir) == str(tmp_path)

    def test_accepts_mock_with_state_store_methods(self, tmp_path: Path):
        """Um mock com os métodos de StateStore é aceito como duck-type."""
        builder = MagicMock(spec=PipelineBuilder)
        runner = MagicMock(spec=PipelineRunner)
        config = {"domain_configs": {}}
        metadata = MagicMock()
        state = MagicMock(spec=StateStore)
        state.base_dir = tmp_path

        manager = PipelineManager(
            builder=builder,
            runner=runner,
            config=config,
            state_store=state,
            metadata_service=metadata,
        )

        assert isinstance(manager, PipelineManager)

    def test_manager_builds_lake_from_base_dir(self, tmp_path: Path):
        """Quando state_store tem base_dir, manager constroi _lake a partir dele."""
        builder = MagicMock(spec=PipelineBuilder)
        runner = MagicMock(spec=PipelineRunner)
        config = {"domain_configs": {}}
        metadata = MagicMock()
        state = MagicMock(spec=StateStore)
        state.base_dir = tmp_path

        manager = PipelineManager(
            builder=builder,
            runner=runner,
            config=config,
            state_store=state,
            metadata_service=metadata,
        )

        # _lake foi construído a partir do base_dir (via from_sink)
        assert manager._lake is not None
        assert manager._lake.base_dir == tmp_path
