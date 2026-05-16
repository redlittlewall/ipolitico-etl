"""Fatiamento opcional quando o dump Bulk cobre período maior que a janela CLI."""

from __future__ import annotations

import polars as pl


def apply_bulk_temporal_filter(
    df: pl.DataFrame, column: str, lo_iso: str, hi_iso: str
) -> pl.DataFrame:
    """Compara lado a lado em YYYY-MM-DD (coluna texto ou Datetime)."""
    if df.is_empty() or column not in df.columns:
        return df

    lo_day = lo_iso[:10]
    hi_day = hi_iso[:10]
    dtype = df.schema[column]
    is_dt = dtype == pl.Datetime or str(dtype).lower().startswith("datetime")

    cmp_col = (
        pl.col(column).dt.strftime("%Y-%m-%d")
        if is_dt
        else pl.col(column).cast(pl.Utf8, strict=False).str.strip_chars().str.slice(0, 10)
    )
    return df.filter((cmp_col >= lo_day) & (cmp_col <= hi_day))
