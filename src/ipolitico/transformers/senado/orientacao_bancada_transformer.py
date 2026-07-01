"""Transformador para o domínio ORIENTACAO_BANCADA — explode votações em registros por partido."""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer


class SenadoOrientacaoBancadaTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de votações com orientação de bancada.

    O DataFrame de entrada contém 1 linha por votação, com o campo
    ``orientacoesLideranca`` (array de structs com ``partido`` e ``voto``).
    O transformer explode esse array, resultando em 1 linha por
    (votação, partido), e mapeia os campos para o contrato Silver.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma votações para o formato Silver (1 linha por partido).

        Args:
            df: DataFrame com 1 linha/votação e coluna array
                ``orientacoesLideranca``.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme o contrato
            Silver, ou DataFrame vazio se a entrada for vazia.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.ORIENTACAO_BANCADA.value]

        # 1. Explode o array orientacoesLideranca → 1 linha por partido
        if "orientacoesLideranca" in df.columns:
            df = df.explode("orientacoesLideranca").with_columns(
                pl.col("orientacoesLideranca").struct.field("partido").alias("sigla_partido"),
                pl.col("orientacoesLideranca").struct.field("voto").alias("orientacao"),
            )

        # 2. Mapeamento flat API → Silver
        mappings: list[tuple[str, str, type[pl.DataType]]] = [
            ("codigoVotacaoSve", "codigo_votacao", pl.Int64),
            ("sigla_partido", "sigla_partido", pl.String),
            ("orientacao", "orientacao", pl.String),
        ]

        for api_name, silver_col, dtype in mappings:
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                expr = pl.col(api_name)
                if dtype == pl.Int64:
                    expr = expr.cast(pl.Int64)
                df = df.with_columns(expr.alias(silver_col))
            else:
                df = df.with_columns(pl.lit(None).alias(silver_col))

        # 3. Extrai data_sessao da dataInicioVotacao (parte ISO date)
        if "dataInicioVotacao" in df.columns:
            df = df.with_columns(pl.col("dataInicioVotacao").str.slice(0, 10).alias("data_sessao"))
        else:
            df = df.with_columns(pl.lit(None).alias("data_sessao"))

        # 4. codigo_materia não está disponível na API atual — mantém null
        df = df.with_columns(pl.lit(None).alias("codigo_materia"))

        # 5. Preenche colunas faltantes no contrato
        for col in contract:
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
