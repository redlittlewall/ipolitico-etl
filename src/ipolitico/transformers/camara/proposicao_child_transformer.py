import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


class CamaraProposicaoChildTransformer(BaseTransformer):
    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        sub = kwargs.get("sub_domain", DomainType.TRAMITACOES.value)
        if "dataHora" in df.columns:
            df = df.with_columns(pl.col("dataHora").str.to_datetime(strict=False))
        if sub == DomainType.PROPOSICOES_VOTACOES.value and "data" in df.columns:
            df = df.with_columns(pl.col("data").str.to_datetime(strict=False))
        if sub == DomainType.PROPOSICOES_VOTACOES.value and "id" in df.columns:
            df = df.with_columns(pl.col("id").cast(pl.String, strict=False))

        contract = SILVER_SCHEMAS[sub]
        try:
            for col in contract:
                if col not in df.columns:
                    df = df.with_columns(pl.lit(None).alias(col))
            return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
        except Exception as e:
            logger.error("[%s] Contrato Silver: %s", sub.upper(), e)
            return pl.DataFrame()
