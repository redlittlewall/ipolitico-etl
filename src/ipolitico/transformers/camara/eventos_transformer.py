import json
import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


class CamaraEventosTransformer(BaseTransformer):
    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        if "orgaos" in df.columns:
            dtype = df.schema["orgaos"]

            def _orgaos_json(v: Any) -> str | None:
                if v is None:
                    return None
                if hasattr(v, "to_list"):
                    v = v.to_list()
                if hasattr(v, "to_dicts"):
                    v = v.to_dicts()
                return json.dumps(v, ensure_ascii=False)

            if isinstance(dtype, pl.List) or dtype == pl.Object or str(dtype).startswith("List"):
                df = df.with_columns(
                    pl.col("orgaos").map_elements(_orgaos_json, return_dtype=pl.String)
                )

        for col in ("dataHoraInicio", "dataHoraFim"):
            if col in df.columns:
                df = df.with_columns(pl.col(col).str.to_datetime(strict=False))

        contract = SILVER_SCHEMAS[DomainType.EVENTOS.value]
        try:
            for col in contract:
                if col not in df.columns:
                    df = df.with_columns(pl.lit(None).alias(col))
            return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
        except Exception as e:
            logger.error("[EVENTOS] Contrato Silver: %s", e)
            return pl.DataFrame()
