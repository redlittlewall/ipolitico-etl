import polars as pl
from ipolitico.core.constants import DomainType, LoadStrategy, SourceType
from ipolitico.pipeline.source_router import SourceRouter


def test_incremental_always_api_for_yearly_domains():
    plan = SourceRouter.plan(
        DomainType.DESPESAS,
        LoadStrategy.INCREMENTAL,
        "2009-01-01",
        "2020-12-31",
    )
    assert plan.source_type == SourceType.API


def test_full_load_multi_year_selects_bulk():
    plan = SourceRouter.plan(
        DomainType.DESPESAS,
        LoadStrategy.FULL_LOAD,
        "2009-01-01",
        "2012-12-31",
    )
    assert plan.source_type == SourceType.BULK
    assert plan.bulk_temporal_column == "dataDocumento"


def test_full_load_single_year_stays_api():
    plan = SourceRouter.plan(
        DomainType.DESPESAS,
        LoadStrategy.FULL_LOAD,
        "2024-03-01",
        "2024-10-01",
    )
    assert plan.source_type == SourceType.API


def test_bulk_window_filter():
    from ipolitico.transformers.bulk_window import apply_bulk_temporal_filter

    df = pl.DataFrame({"dataDocumento": ["2024-01-15", "2024-06-01", "2023-12-01"]})
    out = apply_bulk_temporal_filter(df, "dataDocumento", "2024-01-01", "2024-03-31")
    assert out.height == 1
