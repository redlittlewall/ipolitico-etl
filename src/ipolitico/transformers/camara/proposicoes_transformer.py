import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


class CamaraProposicoesTransformer(BaseTransformer):
    """
    Transformer responsável pelas regras de negócio de Proposições Legislativas.

    Aplica castings de datas e padronizações estritas, consolidando as lógicas
    que antes ficavam dispersas nos extratores Bulk e API.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Executa a transformação e tipagem do DataFrame de proposições.

        Args:
            df (pl.DataFrame): DataFrame bruto da camada Bronze.
            **kwargs (Any): Parâmetros de contexto adicionais.

        Returns:
            pl.DataFrame: DataFrame com tipagem corrigida (Silver).
        """
        if df.is_empty():
            return df

        flt = kwargs.get("bulk_temporal_filter")
        if flt:
            from ipolitico.transformers.bulk_window import (
                BulkTemporalFilter,
                apply_bulk_temporal_filter,
            )

            if isinstance(flt, BulkTemporalFilter):
                fc, lo, hi = flt.column, flt.start_iso, flt.end_iso
            else:
                fc, lo, hi = flt  # fallback tuple (deprecated)
            df = apply_bulk_temporal_filter(df, fc, lo, hi)
            if df.is_empty():
                return df

        if "dataApresentacao" in df.columns:
            df = df.with_columns(pl.col("dataApresentacao").str.to_datetime(strict=False))

        # =====================================================================
        # BLINDAGEM ESTRITA DE SCHEMA (Data Contract)
        # =====================================================================
        contract = SILVER_SCHEMAS[DomainType.PROPOSICOES.value]

        try:
            missing_cols = [col for col in contract.keys() if col not in df.columns]
            if missing_cols:
                for missing in missing_cols:
                    if missing == "uriOrgaoNumerador":
                        df = df.with_columns(pl.lit(None).alias("uriOrgaoNumerador"))
                    else:
                        raise ValueError(f"Coluna obrigatória omitida: {missing}")

            df = df.select(
                [pl.col(col).cast(dtype, strict=True) for col, dtype in contract.items()]
            )

        except Exception as e:
            logger.error(f"[ALERTA CÍVICO - PROPOSIÇÕES] Quebra de Contrato da API: {e}")
            return pl.DataFrame()

        return df
