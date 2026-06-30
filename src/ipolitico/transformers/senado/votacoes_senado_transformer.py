"""Transformador para o domínio VOTACOES_SENADO — mapeia campos da API."""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

# Mapeamento dos campos da API → colunas Silver
_FIELD_MAP: dict[str, tuple[str, type]] = {
    "codigoSessaoVotacao": ("votacao_id", pl.Int64),
    "codigoMateria": ("codigo_materia", pl.Int64),
    "idProcesso": ("id_processo", pl.Int64),
    "identificacao": ("identificacao", pl.String),
    "ementa": ("ementa", pl.String),
    "dataApresentacao": ("data_apresentacao", pl.String),
    "dataSessao": ("data_sessao", pl.String),
    "descricaoVotacao": ("descricao_votacao", pl.String),
    "resultadoVotacao": ("resultado", pl.String),
}


class SenadoVotacoesTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de votações do Senado.

    O DataFrame de entrada contém campos flat (sem envelopes XML).
    O transformer renomeia para snake_case, descarta colunas aninhadas
    (como ``informeLegislativo``, ``votos``) e aplica tipagem estrita.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.VOTACOES_SENADO.value]

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
