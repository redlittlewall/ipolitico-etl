import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


class CamaraMembrosTransformer(BaseTransformer):
    """Membros de órgãos e frentes (mesmo layout de campos na API)."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        sub = kwargs.get("sub_domain", DomainType.ORGAOS_MEMBROS.value)
        contract = SILVER_SCHEMAS[sub]
        for col in ("dataInicio", "dataFim"):
            if col in df.columns:
                # Colunas data podem vir como null dtype quando todos valores são
                # null — .str.slice() falha nesse caso, então converte para Utf8
                # antes de tentar qualquer operação de string.
                df = df.with_columns(
                    pl.when(pl.col(col).is_not_null())
                    .then(pl.col(col).cast(pl.Utf8).str.slice(0, 10))
                    .alias(col)
                )

        try:
            for col in contract:
                if col not in df.columns:
                    df = df.with_columns(pl.lit(None).alias(col))
            return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
        except Exception as e:
            logger.error("[%s] Contrato Silver: %s", sub.upper(), e)
            return pl.DataFrame()
