"""Transformador para o domínio VOTOS_SENADO — mapeia campos da API."""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

# Mapeamento dos campos da API → colunas Silver
_FIELD_MAP: dict[str, tuple[str, type]] = {
    "codigoSessaoVotacao": ("votacao_id", pl.Int64),
    "codigoParlamentar": ("codigo_parlamentar", pl.Int64),
    "nomeParlamentar": ("nome_parlamentar", pl.String),
    "siglaPartidoParlamentar": ("sigla_partido", pl.String),
    "siglaUFParlamentar": ("sigla_uf", pl.String),
    "siglaVotoParlamentar": ("voto", pl.String),
}


class SenadoVotosTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de votos do Senado.

    O DataFrame de entrada contém campos flat com o ID da votação
    (``codigoSessaoVotacao``) injetado pelo extrator.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.VOTOS_SENADO.value]

        # ── Renomeia campos disponíveis ─────────────────────────────────────
        for api_name, (silver_col, _dtype) in _FIELD_MAP.items():
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                df = df.rename({api_name: silver_col})

        # ── Adiciona colunas faltantes como null ────────────────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
