import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


def _jsonify_nested(df: pl.DataFrame) -> pl.DataFrame:
    """Serializa colunas Struct ou List da API para string (contrato Silver).

    Usa expressões nativas Polars (struct.json_encode, list.eval) em vez de
    map_elements para preservar paralelismo vetorizado.

    Args:
        df: DataFrame com possíveis colunas aninhadas.

    Returns:
        DataFrame com colunas aninhadas convertidas para string. Colunas não
        Struct/List permanecem inalteradas.
    """
    for col in df.columns:
        dtype = df.schema[col]
        if isinstance(dtype, pl.Struct):
            df = df.with_columns(pl.col(col).struct.json_encode())
        elif isinstance(dtype, pl.List):
            inner = dtype.inner
            if isinstance(inner, pl.Struct):
                df = df.with_columns(
                    pl.format(
                        "[{}]",
                        pl.col(col).list.eval(pl.element().struct.json_encode()).list.join(","),
                    ).alias(col)
                )
            else:
                # Lista não-Struct (ex: List[String]) — serializa como JSON
                df = df.with_columns(pl.col(col).list.join(","))
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
