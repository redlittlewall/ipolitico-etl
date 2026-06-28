import logging
from typing import Any, Dict

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
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

        for old, new in (("Id", "id"), ("ID", "id")):
            if old in df.columns and "id" not in df.columns:
                df = df.rename({old: "id"})

        if "id" not in df.columns and "uri" in df.columns:
            df = df.with_columns(
                pl.col("uri")
                .str.extract(r"/deputados/(\d+)", 1)
                .cast(pl.Int64, strict=False)
                .alias("id")
            )

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
        contract = SILVER_SCHEMAS[DomainType.DEPUTADOS.value]

        try:
            missing_cols = [col for col in contract.keys() if col not in df.columns]
            if missing_cols:
                for missing in missing_cols:
                    if missing == "email":
                        df = df.with_columns(pl.lit(None).alias("email"))
                    else:
                        raise ValueError(f"Coluna obrigatória omitida pela API: {missing}")

            df = df.select(
                [pl.col(col).cast(dtype, strict=True) for col, dtype in contract.items()]
            )

        except Exception as e:
            logger.error(f"[ALERTA CÍVICO - DEPUTADOS] Quebra de Contrato da API: {e}")
            return pl.DataFrame()

        return df
