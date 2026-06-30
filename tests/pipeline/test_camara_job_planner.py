from unittest.mock import MagicMock

from ipolitico.core.constants import DomainType, SourceType
from ipolitico.pipeline.planners.camara_jobs import JobPlanner
from ipolitico.pipeline.source_router import ExtractionPlan


def test_despesas_bulk_jobs_one_row_per_year():
    store = MagicMock()
    lake = MagicMock()
    planner = JobPlanner(store, lake)
    plan = ExtractionPlan(source_type=SourceType.BULK)
    jobs, mapper = planner.build(
        DomainType.DESPESAS,
        "2024-01-15",
        "2026-03-10",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    assert [mapper(j) for j in jobs] == [{"year": 2024}, {"year": 2025}, {"year": 2026}]


def test_proposicoes_api_monthly_jobs_march_has_31_days():
    store = MagicMock()
    planner = JobPlanner(store, None)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, mapper = planner.build(
        DomainType.PROPOSICOES,
        "2024-03-01",
        "2024-03-31",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    assert len(jobs) == 1
    m = mapper(jobs[0])
    assert m["start_date"] == "2024-03-01"
    assert m["end_date"] == "2024-03-31"


def test_votos_planner_uses_windowed_votacao_ids():
    store = MagicMock()
    lake = MagicMock()
    lake.list_votacao_ids_silver_or_gold.return_value = ["a", "b"]
    planner = JobPlanner(store, lake)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, _ = planner.build(
        DomainType.VOTOS,
        "2024-03-01",
        "2024-03-31",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    lake.list_votacao_ids_silver_or_gold.assert_called_once_with("2024-03-01", "2024-03-31")
    assert len(jobs) == 1
    assert jobs[0]["votacao_ids"] == ["a", "b"]


def test_despesas_api_jobs_skip_existing_pairs():
    store = MagicMock()
    lake = MagicMock()
    lake.list_deputy_ids_for_legislature_bounds.return_value = [1]
    lake.list_deputy_expense_year_pairs.return_value = {(1, 2024)}
    planner = JobPlanner(store, lake)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, _ = planner.build(
        DomainType.DESPESAS,
        "2024-01-01",
        "2024-12-31",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    assert jobs == []


def test_profissoes_jobs_one_per_deputy():
    store = MagicMock()
    store.get_existing_ids.return_value = []
    lake = MagicMock()
    lake.list_deputy_ids_for_legislature_bounds.return_value = [100, 200]
    lake.list_deputy_ids_in_child_table.return_value = set()
    planner = JobPlanner(store, lake)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, mapper = planner.build(
        DomainType.PROFISSÕES,
        "2024-01-01",
        "2024-12-31",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    assert len(jobs) == 2
    assert mapper(jobs[0]) == {"deputado_id": 100}


def test_tramitacoes_planner_batches_proposicao_ids():
    store = MagicMock()
    lake = MagicMock()
    lake.list_proposicao_ids_silver_or_gold.return_value = list(range(30))
    lake.list_proposicao_ids_with_child_materialized.return_value = set()
    planner = JobPlanner(store, lake)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, mapper = planner.build(
        DomainType.TRAMITACOES,
        "2024-03-01",
        "2024-03-31",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    assert len(jobs) == 2
    assert len(mapper(jobs[0])["proposicao_ids"]) == 25
    assert len(mapper(jobs[1])["proposicao_ids"]) == 5


def test_blocos_full_load_one_job_per_legislature():
    from ipolitico.core.constants import EARLIEST_DATE_MAP

    store = MagicMock()
    planner = JobPlanner(store, None)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, mapper = planner.build(
        DomainType.BLOCOS,
        EARLIEST_DATE_MAP[DomainType.BLOCOS],
        "2026-05-15",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    assert len(jobs) == 57
    assert mapper(jobs[0]) == {"legislatura_id": 1}


def test_orientacoes_planner_batches_votacao_ids():
    store = MagicMock()
    lake = MagicMock()
    lake.list_votacao_ids_silver_or_gold.return_value = ["v1", "v2"]
    lake.list_votacao_ids_with_orientacoes_materialized.return_value = set()
    planner = JobPlanner(store, lake)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, mapper = planner.build(
        DomainType.ORIENTACOES,
        "2024-03-01",
        "2024-03-31",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    assert len(jobs) == 1
    assert mapper(jobs[0]) == {"votacao_ids": ["v1", "v2"]}


def test_orgaos_membros_planner_passes_window():
    store = MagicMock()
    lake = MagicMock()
    lake.list_orgao_ids_in_window.return_value = [10, 20]
    lake.list_entity_ids_with_child_materialized.return_value = set()
    planner = JobPlanner(store, lake)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, mapper = planner.build(
        DomainType.ORGAOS_MEMBROS,
        "2024-01-01",
        "2024-06-30",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    m = mapper(jobs[0])
    assert m["orgao_ids"] == [10, 20]
    assert m["start_date"] == "2024-01-01"
    assert m["end_date"] == "2024-06-30"


def test_eventos_deputados_planner_batches_evento_ids():
    store = MagicMock()
    lake = MagicMock()
    lake.list_evento_ids_silver_or_gold.return_value = [1, 2, 3]
    lake.list_entity_ids_with_child_materialized.return_value = set()
    planner = JobPlanner(store, lake)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, mapper = planner.build(
        DomainType.EVENTOS_DEPUTADOS,
        "2024-03-01",
        "2024-03-31",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    assert len(jobs) == 1
    assert mapper(jobs[0]) == {"evento_ids": [1, 2, 3]}


def test_referencias_planner_single_job():
    store = MagicMock()
    planner = JobPlanner(store, None)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, mapper = planner.build(
        DomainType.REFERENCIAS,
        "2024-01-01",
        "2024-12-31",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    assert len(jobs) == 1
    assert len(mapper(jobs[0])["routes"]) >= 10
