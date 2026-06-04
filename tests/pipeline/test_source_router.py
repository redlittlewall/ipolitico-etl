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


# ── SourceRouter: snapshot domains (expansão) ─────────────────────────────────


def test_snapshot_full_load_selects_bulk():
    """
    [SNAPSHOT BULK] Domínio snapshot (ex: frentes) em FULL_LOAD deve usar Bulk.
    """
    plan = SourceRouter.plan(
        DomainType.FRENTES,
        LoadStrategy.FULL_LOAD,
        "2003-01-01",
        "2026-12-31",
    )
    assert plan.source_type == SourceType.BULK


def test_snapshot_full_load_orgaos():
    """
    [SNAPSHOT BULK] orgaos (snapshot) em FULL_LOAD deve usar Bulk.
    """
    plan = SourceRouter.plan(
        DomainType.ORGAOS,
        LoadStrategy.FULL_LOAD,
        "1946-02-01",
        "2026-12-31",
    )
    assert plan.source_type == SourceType.BULK


def test_snapshot_incremental_stays_api():
    """
    [SNAPSHOT API] Domínio snapshot em INCREMENTAL deve usar API.
    """
    plan = SourceRouter.plan(
        DomainType.FRENTES,
        LoadStrategy.INCREMENTAL,
        "2025-01-01",
        "2025-03-01",
    )
    assert plan.source_type == SourceType.API


def test_yearly_snapshot_not_in_yearly_group_still_routes():
    """
    [SNAPSHOT API] Domínio snapshot não listado em _BULK_YEARLY_DOMAINS
    não deve ser bloqueado pelo router.
    """
    plan = SourceRouter.plan(
        DomainType.LEGISLATURAS,
        LoadStrategy.FULL_LOAD,
        "2003-01-01",
        "2026-12-31",
    )
    assert plan.source_type == SourceType.BULK


def test_eventos_yearly_full_load_multi_year_selects_bulk():
    """
    [YEARLY BULK] eventos é anual: full load multi-ano deve usar Bulk.
    """
    plan = SourceRouter.plan(
        DomainType.EVENTOS,
        LoadStrategy.FULL_LOAD,
        "2020-01-01",
        "2025-12-31",
    )
    assert plan.source_type == SourceType.BULK
    assert plan.bulk_temporal_column == "dataHoraInicio"


def test_eventos_yearly_full_load_single_year_stays_api():
    """
    [YEARLY API] eventos anual: full load de um ano apenas deve usar API.
    """
    plan = SourceRouter.plan(
        DomainType.EVENTOS,
        LoadStrategy.FULL_LOAD,
        "2025-06-01",
        "2025-12-01",
    )
    assert plan.source_type == SourceType.API


def test_eventos_incremental_uses_api():
    """
    [YEARLY API] eventos anual: incremental deve sempre usar API.
    """
    plan = SourceRouter.plan(
        DomainType.EVENTOS,
        LoadStrategy.INCREMENTAL,
        "2025-01-01",
        "2025-06-30",
    )
    assert plan.source_type == SourceType.API
