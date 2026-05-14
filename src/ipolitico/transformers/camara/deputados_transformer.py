import logging
from typing import Any, Dict

import polars as pl

from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


class CamaraDeputadosTransformer(BaseTransformer):
    """
    Transformer responsável pela padronização dos dados de Deputados Federais.

    Gere a lista principal de deputados, extração de Chaves Primárias baseadas
    em URIs e serialização de estruturas complexas para salvar no banco/DataLake.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Dict[str, Any]) -> pl.DataFrame:
        if df.is_empty():
            return df

        # Padronização de Nomes
        mapping = {
            "uri": "url_perfil",
            "urlFoto": "url_foto",
            "siglaUf": "uf",
            "siglaPartido": "partido",
        }
        df = df.rename({k: v for k, v in mapping.items() if k in df.columns})

        # =====================================================================
        # BLINDAGEM ESTRITA DE SCHEMA (Data Contract)
        # =====================================================================
        FINAL_SCHEMA = {
            "id": pl.Int64,
            "nome": pl.String,
            "partido": pl.String,
            "uf": pl.String,
            "idLegislatura": pl.Int64,
            "url_foto": pl.String,
            "email": pl.String,
        }

        try:
            missing_cols = [col for col in FINAL_SCHEMA.keys() if col not in df.columns]
            if missing_cols:
                for missing in missing_cols:
                    if missing == "email":
                        df = df.with_columns(pl.lit(None).alias("email"))
                    else:
                        raise ValueError(f"Coluna obrigatória omitida pela API: {missing}")

            df = df.select(
                [pl.col(col).cast(dtype, strict=True) for col, dtype in FINAL_SCHEMA.items()]
            )

        except Exception as e:
            logger.error(f"[ALERTA CÍVICO - DEPUTADOS] Quebra de Contrato da API: {e}")
            return pl.DataFrame()

        return df
