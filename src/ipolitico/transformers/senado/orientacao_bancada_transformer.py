"""Transformador para o domínio ORIENTACAO_BANCADA — mapeia campos da API do Senado."""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

# Mapeamento dos campos da API → colunas Silver
_FIELD_MAP: dict[str, tuple[str, type]] = {
    "dataSessao": ("data_sessao", pl.String),
    "codigoMateria": ("codigo_materia", pl.Int64),
    "siglaPartido": ("sigla_partido", pl.String),
    "orientacao": ("orientacao", pl.String),
    "codigoVotacao": ("codigo_votacao", pl.Int64),
}


class SenadoOrientacaoBancadaTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de orientação de bancada do Senado.

    O DataFrame de entrada contém campos flat (sem envelopes XML).
    O transformer renomeia PascalCase para snake_case, descarta colunas
    não mapeadas e aplica tipagem estrita conforme o contrato Silver.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma orientações de bancada para o contrato Silver.

        Args:
            df: DataFrame bruto da API (colunas PascalCase).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme SILVER_SCHEMAS.
            Retorna DataFrame vazio se a entrada for vazia.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.ORIENTACAO_BANCADA.value]

        # Renomeia campos disponíveis
        for api_name, (silver_col, _dtype) in _FIELD_MAP.items():
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                df = df.rename({api_name: silver_col})

        # Adiciona colunas faltantes como null
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
