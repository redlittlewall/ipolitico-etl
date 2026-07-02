"""Tests for ComissaoChildStrategy and its STRATEGY_REGISTRY registration."""

from unittest.mock import MagicMock

from ipolitico.core.constants import DomainType, SourceType
from ipolitico.core.domain_spec import _spec
from ipolitico.pipeline.planners.strategies import (
    ComissaoChildStrategy,
    DefaultWindowStrategy,
    strategy_for,
)


class TestComissaoChildStrategyBehavior:
    """Testa o comportamento da ComissaoChildStrategy.build()."""

    def test_bulk_retorna_um_job(self):
        """Para fonte BULK, build() deve retornar 1 job snapshot."""
        strategy = ComissaoChildStrategy()
        spec = _spec(DomainType.VOTACOES_COMISSAO, wm="dataSessao")
        plan = MagicMock()
        plan.source_type = SourceType.BULK

        jobs, mapper = strategy.build(
            domain=DomainType.VOTACOES_COMISSAO,
            spec=spec,
            start="1991-01-01",
            end="2026-12-31",
            current_leg=57,
            anchor_year=2023,
            extraction_plan=plan,
            state_store=MagicMock(),
            lake=None,
        )

        assert len(jobs) == 1
        assert mapper(jobs[0]) == {}

    def test_sem_lake_aborta(self):
        """Sem lake, build() deve retornar lista vazia."""
        strategy = ComissaoChildStrategy()
        spec = _spec(DomainType.VOTACOES_COMISSAO, wm="dataSessao")
        plan = MagicMock()
        plan.source_type = SourceType.API

        jobs, mapper = strategy.build(
            domain=DomainType.VOTACOES_COMISSAO,
            spec=spec,
            start="1991-01-01",
            end="2026-12-31",
            current_leg=57,
            anchor_year=2023,
            extraction_plan=plan,
            state_store=MagicMock(),
            lake=None,
        )

        assert len(jobs) == 0

    def test_sem_siglas_aborta(self):
        """Se lake.list_ids retorna vazio, build() retorna lista vazia."""
        strategy = ComissaoChildStrategy()
        spec = _spec(DomainType.VOTACOES_COMISSAO, wm="dataSessao")
        plan = MagicMock()
        plan.source_type = SourceType.API
        lake = MagicMock()
        lake.list_ids.return_value = []

        jobs, mapper = strategy.build(
            domain=DomainType.VOTACOES_COMISSAO,
            spec=spec,
            start="1991-01-01",
            end="2026-12-31",
            current_leg=57,
            anchor_year=2023,
            extraction_plan=plan,
            state_store=MagicMock(),
            lake=lake,
        )

        assert len(jobs) == 0
        lake.list_ids.assert_called_once_with(
            table_name=DomainType.COMISSOES_SENADO.value,
            layer="silver",
            column="sigla",
        )

    def test_com_siglas_gera_jobs(self):
        """Com siglas no lake, gera 1 job por sigla com janela temporal."""
        strategy = ComissaoChildStrategy()
        spec = _spec(DomainType.VOTACOES_COMISSAO, wm="dataSessao")
        plan = MagicMock()
        plan.source_type = SourceType.API
        lake = MagicMock()
        lake.list_ids.return_value = ["CAE", "CCJ", "CAS"]

        jobs, mapper = strategy.build(
            domain=DomainType.VOTACOES_COMISSAO,
            spec=spec,
            start="1991-01-01",
            end="2026-12-31",
            current_leg=57,
            anchor_year=2023,
            extraction_plan=plan,
            state_store=MagicMock(),
            lake=lake,
        )

        assert len(jobs) == 3
        assert jobs[0] == {
            "sigla_comissao": "CAE",
            "start_date": "1991-01-01",
            "end_date": "2026-12-31",
        }
        assert jobs[1] == {
            "sigla_comissao": "CCJ",
            "start_date": "1991-01-01",
            "end_date": "2026-12-31",
        }
        assert jobs[2] == {
            "sigla_comissao": "CAS",
            "start_date": "1991-01-01",
            "end_date": "2026-12-31",
        }

    def test_mapper_extrai_kwargs_corretos(self):
        """Mapper deve produzir kwargs: sigla_comissao + start_date + end_date."""
        strategy = ComissaoChildStrategy()
        spec = _spec(DomainType.VOTACOES_COMISSAO, wm="dataSessao")
        plan = MagicMock()
        plan.source_type = SourceType.API
        lake = MagicMock()
        lake.list_ids.return_value = ["CAE"]

        jobs, mapper = strategy.build(
            domain=DomainType.VOTACOES_COMISSAO,
            spec=spec,
            start="2025-01-01",
            end="2025-12-31",
            current_leg=57,
            anchor_year=2023,
            extraction_plan=plan,
            state_store=MagicMock(),
            lake=lake,
        )

        kwargs = mapper(jobs[0])
        assert kwargs == {
            "sigla_comissao": "CAE",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        }


class TestComissaoStrategyRegistration:
    """Testa que VOTACOES_COMISSAO está registrado com ComissaoChildStrategy."""

    def test_votacoes_comissao_registrado(self):
        """VOTACOES_COMISSAO deve estar mapeado para ComissaoChildStrategy."""
        strategy = strategy_for(DomainType.VOTACOES_COMISSAO)
        assert isinstance(strategy, ComissaoChildStrategy)

    def test_outros_dominios_nao_afetados(self):
        """Domínios não relacionados continuam com DefaultWindowStrategy."""
        # PROCESSOS (sem registro explícito para detalhe) → fallback DefaultWindowStrategy
        strategy = strategy_for(DomainType.PROCESSOS)
        assert isinstance(strategy, DefaultWindowStrategy)
