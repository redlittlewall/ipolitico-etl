"""Transformador para o domínio SENADORES_FILIACOES — aplaina filiações partidárias."""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

# Mapeamento API → Silver para filiações
_FIELD_MAP: list[tuple[str, str, type[pl.DataType]]] = [
    ("CodigoParlamentar", "codigo", pl.Int64),
    ("SiglaPartido", "sigla_partido", pl.String),
    ("DataFiliacao", "data_filiacao", pl.String),
    ("DataDesfiliacao", "data_desfiliacao", pl.String),
]


class SenadoFiliacoesTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de filiações partidárias.

    O DataFrame de entrada contém colunas no formato camelCase da API
    (ex: ``SiglaPartido``, ``DataFiliacao``). O transformer renomeia para
    snake_case e aplica a tipagem estrita do contrato Silver.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma dados brutos de filiações para o formato Silver.

        Args:
            df: DataFrame com colunas no formato camelCase da API.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme o contrato
            Silver, ou DataFrame vazio se a entrada for vazia.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.SENADORES_FILIACOES.value]

        # Renomeia campos do mapeamento
        for api_name, silver_col, dtype in _FIELD_MAP:
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                expr = pl.col(api_name)
                if dtype == pl.Int64:
                    expr = expr.cast(pl.Int64)
                df = df.with_columns(expr.alias(silver_col))
            else:
                df = df.with_columns(pl.lit(None).alias(silver_col))

        # Preenche colunas faltantes no contrato
        for col in contract:
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
