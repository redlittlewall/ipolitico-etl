import polars as pl
from ipolitico.transformers.bulk_window import apply_bulk_temporal_filter


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
