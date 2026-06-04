"""Tests for SnapshotWindowStrategy and its STRATEGY_REGISTRY registration."""

from unittest.mock import MagicMock

from ipolitico.core.constants import DomainType
from ipolitico.core.domain_spec import _spec
from ipolitico.pipeline.planners.strategies import (
    SnapshotWindowStrategy,
    strategy_for,
)


class TestSnapshotWindowStrategyBehavior:
    """Testa o comportamento da SnapshotWindowStrategy.build()."""

    def test_build_retorna_um_job(self):
        """build() deve retornar exatamente 1 job para qualquer janela temporal."""
        strategy = SnapshotWindowStrategy()
        spec = _spec(DomainType.FUNCIONARIOS, wm=None)
        mock_plan = MagicMock()
        mock_store = MagicMock()

        jobs, mapper = strategy.build(
            domain=DomainType.FUNCIONARIOS,
            spec=spec,
            start="1826-01-01",
            end="2026-12-31",
            current_leg=57,
            anchor_year=2023,
            extraction_plan=mock_plan,
            state_store=mock_store,
            lake=None,
        )

        assert len(jobs) == 1

    def test_build_job_sem_parametros_temporais(self):
        """O job retornado não deve conter start_date nem end_date."""
        strategy = SnapshotWindowStrategy()
        spec = _spec(DomainType.FUNCIONARIOS, wm=None)
        mock_plan = MagicMock()
        mock_store = MagicMock()

        jobs, mapper = strategy.build(
            domain=DomainType.FUNCIONARIOS,
            spec=spec,
            start="1826-01-01",
            end="2026-12-31",
            current_leg=57,
            anchor_year=2023,
            extraction_plan=mock_plan,
            state_store=mock_store,
            lake=None,
        )

        job = jobs[0]
        assert "start_date" not in job
        assert "end_date" not in job

    def test_build_mapper_retorna_dict_vazio(self):
        """O mapper retornado deve transformar job em kwargs vazios (sem parâmetros temporais)."""
        strategy = SnapshotWindowStrategy()
        spec = _spec(DomainType.FUNCIONARIOS, wm=None)
        mock_plan = MagicMock()
        mock_store = MagicMock()

        jobs, mapper = strategy.build(
            domain=DomainType.FUNCIONARIOS,
            spec=spec,
            start="1826-01-01",
            end="2026-12-31",
            current_leg=57,
            anchor_year=2023,
            extraction_plan=mock_plan,
            state_store=mock_store,
            lake=None,
        )

        kwargs = mapper(jobs[0])
        assert kwargs == {}


class TestSnapshotStrategyRegistration:
    """Testa que os domínios bulk-only snapshot estão registrados com SnapshotWindowStrategy."""

    def test_funcionarios_registrado(self):
        """FUNCIONARIOS deve estar mapeado para SnapshotWindowStrategy."""
        strategy = strategy_for(DomainType.FUNCIONARIOS)
        assert isinstance(strategy, SnapshotWindowStrategy)

    def test_tecad_categorias_registrado(self):
        """TECAD_CATEGORIAS deve estar mapeado para SnapshotWindowStrategy."""
        strategy = strategy_for(DomainType.TECAD_CATEGORIAS)
        assert isinstance(strategy, SnapshotWindowStrategy)

    def test_tecad_termos_registrado(self):
        """TECAD_TERMOS deve estar mapeado para SnapshotWindowStrategy."""
        strategy = strategy_for(DomainType.TECAD_TERMOS)
        assert isinstance(strategy, SnapshotWindowStrategy)
