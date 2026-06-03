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

        if sub in (
            DomainType.EVENTOS_VOTACOES.value,
            DomainType.ORGAOS_EVENTOS.value,
            DomainType.ORGAOS_VOTACOES.value,
        ):
            if "dataHoraInicio" in df.columns:
                df = df.with_columns(pl.col("dataHoraInicio").str.to_datetime(strict=False))
            if "data" in df.columns:
                df = df.with_columns(pl.col("data").str.to_datetime(strict=False))
        if sub == DomainType.EVENTOS_VOTACOES.value and "id" in df.columns:
            df = df.with_columns(pl.col("id").cast(pl.String, strict=False))

        for col in df.columns:
            dtype = df.schema[col]
            if col in _NESTED_JSON_COLS or isinstance(dtype, pl.Struct):
                if isinstance(dtype, pl.Struct):
                    df = df.with_columns(pl.col(col).struct.json_encode().alias(col))

        for col, dtype in contract.items():
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
