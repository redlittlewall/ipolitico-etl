from unittest.mock import MagicMock

from ipolitico.core.constants import DomainType, SourceType
from ipolitico.pipeline.planners.camara_jobs import CamaraJobPlanner
from ipolitico.pipeline.source_router import ExtractionPlan


def test_despesas_bulk_jobs_one_row_per_year():
    store = MagicMock()
    lake = MagicMock()
    planner = CamaraJobPlanner(store, lake)
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
    planner = CamaraJobPlanner(store, None)
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
