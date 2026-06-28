import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


class CamaraOrientacoesTransformer(BaseTransformer):
    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        contract = SILVER_SCHEMAS[DomainType.ORIENTACOES.value]
        try:
            for col in contract:
                if col not in df.columns:
                    df = df.with_columns(pl.lit(None).alias(col))
            if "votacao_id" in df.columns:
                df = df.with_columns(pl.col("votacao_id").cast(pl.String, strict=False))
            return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
        except Exception as e:
            logger.error("[ORIENTACOES] Contrato Silver: %s", e)
            return pl.DataFrame()
