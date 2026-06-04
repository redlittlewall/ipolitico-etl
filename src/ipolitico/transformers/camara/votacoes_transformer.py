import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiParams, DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


def _normalize_nested_to_string(df: pl.DataFrame, column: str) -> pl.DataFrame:
    """Converte coluna Struct da API em string para o contrato Silver.

    Usa expressões nativas Polars (struct.json_encode / struct.field) em vez
    de map_elements para preservar paralelismo vetorizado.

    Args:
        df: DataFrame com a coluna a normalizar.
        column: Nome da coluna que pode ser Struct.

    Returns:
        DataFrame com a coluna convertida para string ou extraída.
        Retorna o DataFrame inalterado se a coluna não existir ou não for Struct.
    """
    if column not in df.columns:
        return df
    dtype = df.schema[column]
    if isinstance(dtype, pl.Struct):
        fields = dtype.fields
        if any(f.name == "uri" for f in fields):
            return df.with_columns(pl.col(column).struct.field("uri").alias(column))
        return df.with_columns(pl.col(column).struct.json_encode().alias(column))
    return df


class CamaraVotacoesTransformer(BaseTransformer):
    """
    Transformer responsável pelo domínio de Votações e Votos.

    Lida com o achatamento (flattening) de estruturas JSON aninhadas da API
    e renomeação de colunas. Aplica o contrato de dados estrito para garantir
    a governança do Data Lake.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        sub_domain = kwargs.get("sub_domain", DomainType.VOTACOES.value)

        if sub_domain == DomainType.VOTACOES.value:
            return self._transform_votacoes(df, kwargs)
        if sub_domain == DomainType.VOTOS.value:
            return self._transform_votos(df)

        return df

    def _transform_votacoes(self, df: pl.DataFrame, kwargs: dict) -> pl.DataFrame:
        date_cols = ["data", "dataHoraRegistro"]
        transformations = [
            pl.col(c).str.to_datetime(strict=False) for c in date_cols if c in df.columns
        ]
        if transformations:
            df = df.with_columns(transformations)

        df = _normalize_nested_to_string(df, "proposicaoObjeto")

        bf = kwargs.get("bulk_temporal_filter")
        if bf:
            from ipolitico.transformers.bulk_window import (
                BulkTemporalFilter,
                apply_bulk_temporal_filter,
            )

            if isinstance(bf, BulkTemporalFilter):
                fc, lo, hi = bf.column, bf.start_iso, bf.end_iso
            else:
                fc, lo, hi = bf  # fallback tuple (deprecated)
            df = apply_bulk_temporal_filter(df, fc, lo, hi)
            if df.is_empty():
                return pl.DataFrame()

        schema_vot = SILVER_SCHEMAS[DomainType.VOTACOES.value]

        try:
            missing_cols = [col for col in schema_vot.keys() if col not in df.columns]
            for missing in missing_cols:
                if missing in ("uriEvento", "aprovacao", "proposicaoObjeto"):
                    df = df.with_columns(pl.lit(None).alias(missing))
                else:
                    raise ValueError(f"Coluna obrigatória omitida na Votação: {missing}")

            if "aprovacao" in df.columns:
                df = df.with_columns(pl.col("aprovacao").cast(pl.Int64, strict=False))

            df = df.select(
                [pl.col(col).cast(dtype, strict=False) for col, dtype in schema_vot.items()]
            )

        except Exception as e:
            logger.error(f"[ALERTA CÍVICO - VOTACOES] Quebra de Contrato: {e}")
            return pl.DataFrame()

        return df

    def _transform_votos(self, df: pl.DataFrame) -> pl.DataFrame:
        if "votacao_id" not in df.columns:
            logger.error("[ALERTA CÍVICO - VOTOS] Coluna 'votacao_id' ausente no DataFrame bruto.")
            return pl.DataFrame()

        dep_col = "deputado_"
        if dep_col in df.columns and isinstance(df.schema[dep_col], pl.Struct):
            df = df.with_columns(
                [
                    pl.col(dep_col).struct.field("id").alias(ApiParams.DEPUTADO_ID.value),
                    pl.col(dep_col).struct.field("siglaPartido").alias("partido"),
                    pl.col(dep_col).struct.field("siglaUf").alias("uf"),
                ]
            ).drop(dep_col)

        mapping = {"idDeputado": ApiParams.DEPUTADO_ID.value}
        df = df.rename({k: v for k, v in mapping.items() if k in df.columns})

        schema_votos = SILVER_SCHEMAS[DomainType.VOTOS.value]

        try:
            missing_cols = [col for col in schema_votos.keys() if col not in df.columns]
            if missing_cols:
                raise ValueError(f"A API omitiu dados essenciais do Voto: {missing_cols}")

            df = df.select(
                [pl.col(col).cast(dtype, strict=False) for col, dtype in schema_votos.items()]
            )

        except Exception as e:
            logger.error(f"[ALERTA CÍVICO - VOTOS] Quebra de Contrato no Voto Nominal: {e}")
            return pl.DataFrame()

        return df
