import polars as pl
from ipolitico.transformers.bulk_window import (
    BulkTemporalFilter,
    apply_bulk_temporal_filter,
)


def test_apply_bulk_temporal_filter_string_dates():
    df = pl.DataFrame(
        {
            "dataDocumento": ["2024-03-01", "2024-02-28", "2024-03-31", "2024-03-10"],
        }
    )
    out = apply_bulk_temporal_filter(df, "dataDocumento", "2024-03-01", "2024-03-15")
    assert out.height == 2
    assert set(out["dataDocumento"].to_list()) == {"2024-03-01", "2024-03-10"}


def test_apply_bulk_temporal_filter_datetime_column():
    df = pl.DataFrame(
        {
            "data": [
                "2024-03-01T10:00:00",
                "2024-02-01T10:00:00",
            ]
        }
    ).with_columns(pl.col("data").str.to_datetime())
    out = apply_bulk_temporal_filter(df, "data", "2024-03-01", "2024-03-31")
    assert out.height == 1


def test_bulk_temporal_filter_dataclass():
    """BulkTemporalFilter é construtível e expõe atributos nomeados."""
    filtro = BulkTemporalFilter(
        column="dataDocumento", start_iso="2023-01-01", end_iso="2023-12-31"
    )
    assert filtro.column == "dataDocumento"
    assert filtro.start_iso == "2023-01-01"
    assert filtro.end_iso == "2023-12-31"


def test_bulk_temporal_filter_used_via_kwargs():
    """Transformer aceita BulkTemporalFilter via kwargs (simula fluxo real)."""

    class _Dummy:
        def transform(self, df, **kwargs):
            bf = kwargs.get("bulk_temporal_filter")
            if bf:
                return apply_bulk_temporal_filter(df, bf.column, bf.start_iso, bf.end_iso)
            return df

    transformer = _Dummy()
    df = pl.DataFrame({"data": ["2024-06-01", "2024-07-01", "2025-01-01"]})
    filtro = BulkTemporalFilter(column="data", start_iso="2024-06-01", end_iso="2024-12-31")
    result = transformer.transform(df, bulk_temporal_filter=filtro)
    assert result.height == 2
    assert result["data"].to_list() == ["2024-06-01", "2024-07-01"]
