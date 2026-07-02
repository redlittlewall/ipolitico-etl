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


# ─── BoundedWindowStrategy (Senado emendas/documentos) ─────────────────────


def _chunk_count_approx(total_days: int, chunk_size: int) -> int:
    """Quantos chunks M × chunk_size dias cobrem total_days."""
    import math

    return math.ceil(total_days / chunk_size)


def test_bounded_full_historical_emendas():
    """Janela 1949→2026 com max_window_days=365 produz chunks ≤ 365d."""
    from datetime import date

    store = MagicMock()
    planner = JobPlanner(store, None)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, mapper = planner.build(
        DomainType.PROCESSOS_EMENDAS,
        "1949-01-01",
        "2026-06-30",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    # ~77 anos × 365 = ~28300 dias → ~78 chunks de 365d
    assert 70 <= len(jobs) <= 90, f"Esperado ~78 chunks, obtido {len(jobs)}"

    for job in jobs:
        start = date.fromisoformat(job["dataInicio"])
        end = date.fromisoformat(job["dataFim"])
        delta = (end - start).days + 1
        assert delta <= 365, f"Chunk {job} tem {delta} dias (> 365)"

    # Verifica cobertura sem gaps
    assert mapper(jobs[0])["start_date"] == "1949-01-01"
    last_end = mapper(jobs[-1])["end_date"]
    assert last_end == "2026-06-30", f"Último chunk termina em {last_end}"

    from datetime import timedelta

    # Verifica sequência — cada chunk começa 1 dia após o anterior
    for i in range(1, len(jobs)):
        prev_end = date.fromisoformat(jobs[i - 1]["dataFim"])
        cur_start = date.fromisoformat(jobs[i]["dataInicio"])
        expected_start = prev_end + timedelta(days=1)
        assert cur_start == expected_start, (
            f"Gap entre chunk {i - 1} (ends {prev_end}) e chunk {i} (starts {cur_start}); "
            f"expected {expected_start}"
        )


def test_bounded_full_historical_documentos():
    """Janela 1949→2026 com max_window_days=180 produz chunks ≤ 180d."""
    from datetime import date

    store = MagicMock()
    planner = JobPlanner(store, None)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, mapper = planner.build(
        DomainType.PROCESSOS_DOCUMENTOS,
        "1949-01-01",
        "2026-06-30",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    # ~28300 dias → ~158 chunks de 180d
    assert 140 <= len(jobs) <= 170, f"Esperado ~158 chunks, obtido {len(jobs)}"

    for job in jobs:
        start = date.fromisoformat(job["dataInicio"])
        end = date.fromisoformat(job["dataFim"])
        delta = (end - start).days + 1
        assert delta <= 180, f"Chunk {job} tem {delta} dias (> 180)"


def test_bounded_window_smaller_than_limit():
    """Janela menor que o limite gera 1 chunk."""
    store = MagicMock()
    planner = JobPlanner(store, None)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, mapper = planner.build(
        DomainType.PROCESSOS_EMENDAS,
        "2025-01-01",
        "2025-06-30",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    assert len(jobs) == 1
    assert mapper(jobs[0]) == {"start_date": "2025-01-01", "end_date": "2025-06-30"}


def test_bounded_window_single_day():
    """Janela de 1 dia gera 1 chunk."""
    store = MagicMock()
    planner = JobPlanner(store, None)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, mapper = planner.build(
        DomainType.PROCESSOS_EMENDAS,
        "2025-06-15",
        "2025-06-15",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    assert len(jobs) == 1
    assert mapper(jobs[0]) == {"start_date": "2025-06-15", "end_date": "2025-06-15"}


def test_bounded_mapper_output():
    """Mapper retorna start_date/end_date para compatibilidade com extractor.

    Usa PROCESSOS_DOCUMENTOS (max_window_days=180) com janela de 90 dias
    para garantir um único chunk.
    """
    store = MagicMock()
    planner = JobPlanner(store, None)
    plan = ExtractionPlan(source_type=SourceType.API)
    jobs, mapper = planner.build(
        DomainType.PROCESSOS_DOCUMENTOS,
        "2025-04-01",
        "2025-06-30",
        current_leg=57,
        anchor_year=2023,
        extraction_plan=plan,
    )
    assert len(jobs) == 1, f"Esperado 1 chunk, obtido {len(jobs)}"
    mapped = mapper(jobs[0])
    assert "start_date" in mapped
    assert "end_date" in mapped
    assert mapped["start_date"] == "2025-04-01"
    assert mapped["end_date"] == "2025-06-30"
