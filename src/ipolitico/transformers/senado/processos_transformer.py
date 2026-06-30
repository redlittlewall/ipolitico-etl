"""Transformador para o domínio PROCESSOS — mapeia campos flat da API."""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

# Mapeamento dos campos flat da API → colunas Silver
_FIELD_MAP: dict[str, tuple[str, type]] = {
    "id": ("id", pl.Int64),
    "codigoMateria": ("codigo_materia", pl.Int64),
    "identificacao": ("identificacao", pl.String),
    "ementa": ("ementa", pl.String),
    "autoria": ("autoria", pl.String),
    "tipoDocumento": ("tipo_documento", pl.String),
    "dataApresentacao": ("data_apresentacao", pl.String),
    "situacaoAtual": ("situacao_atual", pl.String),
    "dataSituacaoAtual": ("data_situacao", pl.String),
    "casaIdentificadora": ("casa_identificadora", pl.String),
    "tramitando": ("tramitando", pl.String),
}


class SenadoProcessosTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de processos.

    O DataFrame de entrada contém campos flat (sem envelopes XML).
    O transformer renomeia para snake_case e aplica tipagem estrita.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.PROCESSOS.value]

        # ── Renomeia e tipa campos disponíveis ──────────────────────────────
        for api_name, (silver_col, _dtype) in _FIELD_MAP.items():
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                df = df.rename({api_name: silver_col})

        # ── Cast dos campos do contrato ─────────────────────────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
