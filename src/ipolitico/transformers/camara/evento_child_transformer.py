import json
import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)

_NESTED_JSON_COLS = frozenset({"proposicao_", "proposicaoRelacionada_", "relator"})


class CamaraEventoChildTransformer(BaseTransformer):
    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        sub = kwargs.get("sub_domain", "")
        contract = SILVER_SCHEMAS.get(sub)
        if not contract:
            return df

        if sub == DomainType.EVENTOS_VOTACOES.value and "data" in df.columns:
            df = df.with_columns(pl.col("data").str.to_datetime(strict=False))
        if sub == DomainType.EVENTOS_VOTACOES.value and "id" in df.columns:
            df = df.with_columns(pl.col("id").cast(pl.String, strict=False))

        for col in df.columns:
            if col in _NESTED_JSON_COLS or df.schema[col] in (pl.Struct, pl.Object):
                df = df.with_columns(
                    pl.col(col)
                    .map_elements(
                        lambda v: json.dumps(v, ensure_ascii=False) if v is not None else None,
                        return_dtype=pl.String,
                    )
                    .alias(col)
                )

        for col, dtype in contract.items():
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
