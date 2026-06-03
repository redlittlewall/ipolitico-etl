import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


class CamaraDiscursosTransformer(BaseTransformer):
    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        if "faseEvento" in df.columns:
            dtype = df.schema["faseEvento"]
            if isinstance(dtype, pl.Struct):
                df = df.with_columns(pl.col("faseEvento").struct.json_encode())

        for col in ("dataHoraInicio", "dataHoraFim"):
            if col in df.columns:
                df = df.with_columns(pl.col(col).str.to_datetime(strict=False))

        contract = SILVER_SCHEMAS[DomainType.DISCURSOS.value]
        try:
            for col in contract:
                if col not in df.columns:
                    df = df.with_columns(pl.lit(None).alias(col))
            return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
        except Exception as e:
            logger.error("[DISCURSOS] Contrato Silver: %s", e)
            return pl.DataFrame()
