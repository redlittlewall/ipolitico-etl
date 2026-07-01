"""Transformador para o domínio SENADORES_MANDATOS — aplaina mandatos de senador."""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

# Mapeamento API → Silver para mandatos
_FIELD_MAP: list[tuple[str, str, type[pl.DataType]]] = [
    ("CodigoParlamentar", "codigo", pl.Int64),
    ("CodigoMandato", "codigo_mandato", pl.Int64),
    ("Uf", "uf", pl.String),
    ("DescricaoParticipacao", "descricao_participacao", pl.String),
    ("PrimeiraLegislatura", "primeira_legislatura", pl.Int64),
    ("SegundaLegislatura", "segunda_legislatura", pl.Int64),
    ("SiglaPartido", "sigla_partido", pl.String),
    ("DataInicio", "data_inicio", pl.String),
    ("DataFim", "data_fim", pl.String),
]


class SenadoMandatosTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de mandatos de senadores.

    O DataFrame de entrada contém colunas no formato camelCase da API
    (ex: ``CodigoMandato``, ``Uf``). O transformer renomeia para snake_case
    e aplica a tipagem estrita do contrato Silver.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma dados brutos de mandatos para o formato Silver.

        Args:
            df: DataFrame com colunas no formato camelCase da API.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme o contrato
            Silver, ou DataFrame vazio se a entrada for vazia.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.SENADORES_MANDATOS.value]

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
