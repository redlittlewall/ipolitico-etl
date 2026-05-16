import logging
from typing import Any, Dict

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer
from ipolitico.transformers.ceap_bulk import apply_ceap_column_aliases, normalize_document_date_iso

logger = logging.getLogger(__name__)


class CamaraDespesasTransformer(BaseTransformer):
    """
    Transformer responsável pela regra de negócio das Despesas (Cota Parlamentar).

    Padroniza nomes de colunas do Bulk/API, formata datas e converte moeda
    brasileira para tipo numérico seguro (Float64).
    """

    def transform(self, df: pl.DataFrame, **kwargs: Dict[str, Any]) -> pl.DataFrame:
        if df.is_empty():
            return df

        n_in = df.height
        df = apply_ceap_column_aliases(df)
        df = normalize_document_date_iso(df)

        flt = kwargs.get("bulk_temporal_filter")
        if flt:
            from ipolitico.transformers.bulk_window import apply_bulk_temporal_filter

            fc, lo, hi = flt
            df = apply_bulk_temporal_filter(df, fc, lo, hi)
            if df.is_empty():
                logger.warning(
                    "Filtro temporal CEAP (%s a %s) eliminou todas as %s linhas brutas. "
                    "Verifique dataDocumento e a janela CLI.",
                    lo[:10],
                    hi[:10],
                    n_in,
                )
                return df

        for col_moeda in ["valorLiquido", "valorDocumento", "valorGlosa"]:
            if col_moeda in df.columns and df.schema[col_moeda] == pl.String:
                df = df.with_columns(
                    pl.col(col_moeda)
                    .str.replace_all(r"\.", "")
                    .str.replace(r",", ".")
                    .alias(col_moeda)
                )

        contract = SILVER_SCHEMAS[DomainType.DESPESAS.value]

        try:
            cols_to_keep = [c for c in contract.keys() if c in df.columns]
            df = df.select(cols_to_keep)

            for expected_col, dtype in contract.items():
                if expected_col not in df.columns:
                    df = df.with_columns(pl.lit(None).alias(expected_col))

            if "tipoDocumento" in df.columns:
                df = df.with_columns(pl.col("tipoDocumento").cast(pl.String, strict=False))

            df = df.select(
                [pl.col(col).cast(dtype, strict=False) for col, dtype in contract.items()]
            )

            df = df.filter((pl.col("codDocumento").is_not_null()) & (pl.col("valorLiquido") != 0.0))

            if df.is_empty() and n_in > 0:
                logger.warning(
                    "Contrato Silver / filtro cívico eliminou %s linhas CEAP brutas "
                    "(codDocumento nulo ou valorLiquido=0).",
                    n_in,
                )

        except Exception as e:
            logger.error(f"[ALERTA CÍVICO] Quebra de Contrato da API detectada: {e}")
            return pl.DataFrame()

        return df
