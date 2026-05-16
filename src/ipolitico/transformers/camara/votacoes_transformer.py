import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiParams, DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


class CamaraVotacoesTransformer(BaseTransformer):
    """
    Transformer responsável pelo domínio de Votações e Votos.

    Lida com o achatamento (flattening) de estruturas JSON aninhadas da API
    e renomeação de colunas. Aplica o contrato de dados estrito para garantir
    a governança do Data Lake.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma dados de votações ou votos, dependendo do contexto.

        Args:
            df (pl.DataFrame): DataFrame bruto oriundo da camada Bronze.
            **kwargs (Any): Parâmetros de contexto. Use `sub_domain=DomainType.VOTOS`
                            para aplicar a lógica de extração de votos individuais.

        Returns:
            pl.DataFrame: DataFrame padronizado e tipado para a camada Silver.
        """
        if df.is_empty():
            return df

        # Uso de Enum para evitar Magic Strings e separar as lógicas
        sub_domain = kwargs.get("sub_domain", DomainType.VOTACOES.value)

        # =====================================================================
        # LÓGICA 1: CABEÇALHOS DAS VOTAÇÕES
        # =====================================================================
        if sub_domain == DomainType.VOTACOES.value:
            # 1. Tratamento de Datas (Robustez contra a string suja da API)
            date_cols = ["data", "dataHoraRegistro"]
            transformations = [
                pl.col(c).str.to_datetime(strict=False) for c in date_cols if c in df.columns
            ]
            if transformations:
                df = df.with_columns(transformations)

            bf = kwargs.get("bulk_temporal_filter")
            if bf:
                from ipolitico.transformers.bulk_window import apply_bulk_temporal_filter

                fc, lo, hi = bf
                df = apply_bulk_temporal_filter(df, fc, lo, hi)
                if df.is_empty():
                    return pl.DataFrame()

            # 2. Contrato de Dados (Schema Enforcement)
            schema_vot = SILVER_SCHEMAS[DomainType.VOTACOES.value]

            try:
                missing_cols = [col for col in schema_vot.keys() if col not in df.columns]
                if missing_cols:
                    # A API frequentemente omite a uriEvento se não houver gravação em vídeo/áudio
                    # Resiliência controlada:
                    for missing in missing_cols:
                        if missing in ["uriEvento", "aprovacao"]:
                            df = df.with_columns(pl.lit(None).alias(missing))
                        else:
                            raise ValueError(f"Coluna obrigatória omitida na Votação: {missing}")

                df = df.select(
                    [pl.col(col).cast(dtype, strict=True) for col, dtype in schema_vot.items()]
                )

            except Exception as e:
                logger.error(f"[ALERTA CÍVICO - VOTACOES] Quebra de Contrato: {e}")
                return pl.DataFrame()

        # =====================================================================
        # LÓGICA 2: VOTOS NOMINAIS (O Problema N+1)
        # =====================================================================
        if sub_domain == DomainType.VOTOS.value:
            if "votacao_id" not in df.columns:
                logger.error(
                    "[ALERTA CÍVICO - VOTOS] Coluna 'votacao_id' ausente no DataFrame bruto."
                    " Extrator falhou."
                )
                return pl.DataFrame()

            # 2. Achatamento do Struct da API (Substitui loops Python lentos)
            dep_col = "deputado_"
            if dep_col in df.columns and isinstance(df.schema[dep_col], pl.Struct):
                df = df.with_columns(
                    [
                        pl.col(dep_col).struct.field("id").alias(ApiParams.DEPUTADO_ID.value),
                        pl.col(dep_col).struct.field("siglaPartido").alias("partido"),
                        pl.col(dep_col).struct.field("siglaUf").alias("uf"),
                    ]
                ).drop(dep_col)

            # 3. Tratamento do Bulk: Tradução de Schema
            mapping = {"idDeputado": ApiParams.DEPUTADO_ID.value}
            df = df.rename({k: v for k, v in mapping.items() if k in df.columns})

            # 4. Contrato de Dados Estrito (Schema Enforcement)
            schema_votos = SILVER_SCHEMAS[DomainType.VOTOS.value]

            try:
                missing_cols = [col for col in schema_votos.keys() if col not in df.columns]
                if missing_cols:
                    raise ValueError(f"A API omitiu dados essenciais do Voto: {missing_cols}")

                df = df.select(
                    [pl.col(col).cast(dtype, strict=True) for col, dtype in schema_votos.items()]
                )

            except Exception as e:
                logger.error(f"[ALERTA CÍVICO - VOTOS] Quebra de Contrato no Voto Nominal: {e}")
                return pl.DataFrame()

        return df
