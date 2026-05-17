import json
import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


def _jsonify_nested(df: pl.DataFrame) -> pl.DataFrame:
    for col in df.columns:
        dtype = df.schema[col]
        if dtype in (pl.Struct, pl.Object, pl.List):
            df = df.with_columns(
                pl.col(col).map_elements(
                    lambda v: json.dumps(v, ensure_ascii=False) if v is not None else None,
                    return_dtype=pl.String,
                )
            )
    return df


class CamaraDetalheTransformer(BaseTransformer):
    r"""Contrato Silver para domínios *\_detalhe (payload enriquecido por ID)."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        sub = kwargs.get("sub_domain", "")
        contract = SILVER_SCHEMAS.get(sub)
        if not contract:
            return df

        df = _jsonify_nested(df)
        for col in ("dataHoraInicio", "dataHoraFim"):
            if col in df.columns:
                df = df.with_columns(pl.col(col).str.to_datetime(strict=False))
        if sub == DomainType.VOTACOES_DETALHE.value and "id" in df.columns:
            df = df.with_columns(pl.col("id").cast(pl.String, strict=False))
        if sub == DomainType.VOTACOES_DETALHE.value and "data" in df.columns:
            df = df.with_columns(pl.col("data").str.to_datetime(strict=False))
        for col in ("dataInicio", "dataFim", "dataNascimento", "dataFalecimento"):
            if col in df.columns:
                df = df.with_columns(pl.col(col).str.slice(0, 10))

        try:
            for col in contract:
                if col not in df.columns:
                    df = df.with_columns(pl.lit(None).alias(col))
            return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
        except Exception as e:
            logger.error("[%s] Contrato Silver: %s", sub.upper(), e)
            return pl.DataFrame()
