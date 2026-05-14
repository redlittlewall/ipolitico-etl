import logging
from typing import Any

import polars as pl

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

        if "dataApresentacao" in df.columns:
            df = df.with_columns(pl.col("dataApresentacao").str.to_datetime(strict=False))

        # =====================================================================
        # BLINDAGEM ESTRITA DE SCHEMA (Data Contract)
        # =====================================================================
        EXPECTED_SCHEMA = {
            "id": pl.Int64,
            "uri": pl.String,
            "siglaTipo": pl.String,
            "numero": pl.Int64,
            "ano": pl.Int64,
            "ementa": pl.String,
            "dataApresentacao": pl.Datetime,
            "uriOrgaoNumerador": pl.String,
        }

        try:
            missing_cols = [col for col in EXPECTED_SCHEMA.keys() if col not in df.columns]
            if missing_cols:
                # O órgão numerador às vezes é nulo para propostas muito antigas
                for missing in missing_cols:
                    if missing == "uriOrgaoNumerador":
                        df = df.with_columns(pl.lit(None).alias("uriOrgaoNumerador"))
                    else:
                        raise ValueError(f"Coluna obrigatória omitida: {missing}")

            df = df.select(
                [pl.col(col).cast(dtype, strict=True) for col, dtype in EXPECTED_SCHEMA.items()]
            )

        except Exception as e:
            logger.error(f"[ALERTA CÍVICO - PROPOSIÇÕES] Quebra de Contrato da API: {e}")
            return pl.DataFrame()

        return df
