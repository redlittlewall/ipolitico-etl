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
                # Alguns discursos não têm dataHoraFim → coluna nula;
                # cast para String primeiro para evitar erro "expected String, got null"
                # quando o Polars infere a coluna como pl.Null (todos os valores nulos).
                # O cast(pl.Utf8) converte pl.Null → String com nulls antes do .str accessor.
                df = df.with_columns(
                    pl.col(col).cast(pl.Utf8).alias(col)  # garante dtype String antes do .str
                )
                df = df.with_columns(
                    pl.when(pl.col(col).is_not_null())
                    .then(pl.col(col).str.to_datetime(strict=False))
                    .otherwise(pl.lit(None, dtype=pl.Datetime))
                    .alias(col)
                )

        contract = SILVER_SCHEMAS[DomainType.DISCURSOS.value]
        try:
            for col in contract:
                if col not in df.columns:
                    df = df.with_columns(pl.lit(None).alias(col))
            return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
        except Exception as e:
            logger.error("[DISCURSOS] Contrato Silver: %s", e)
            return pl.DataFrame()
