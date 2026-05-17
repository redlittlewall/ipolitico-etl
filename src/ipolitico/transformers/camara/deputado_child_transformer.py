"""Normalização Silver para rotas filhas de deputados."""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer


class CamaraDeputadoChildTransformer(BaseTransformer):
    """Aplica contrato Silver por subdomínio (profissoes | ocupacoes)."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        sub = kwargs.get("sub_domain", "")
        contract = SILVER_SCHEMAS.get(sub)
        if not contract:
            return df

        for col, dtype in contract.items():
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
