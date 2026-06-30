"""Transformadores para os domínios de vetos presidenciais — mapeia campos flat da API."""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

# Mapeamento dos campos flat da API → colunas Silver para vetos_presidenciais
_FIELD_MAP_PRESIDENCIAIS: dict[str, tuple[str, type]] = {
    "Codigo": ("codigo", pl.Int64),
    "Ano": ("ano", pl.Int64),
    "Numero": ("numero", pl.String),
    "Tipo": ("tipo", pl.String),
    "CasaOrigem": ("casa_origem", pl.String),
    "SiglaProposicao": ("sigla_proposicao", pl.String),
    "Ementa": ("ementa", pl.String),
    "Autor": ("autor", pl.String),
    "DataApreciacao": ("data_apreciacao", pl.String),
    "Resultado": ("resultado", pl.String),
}

# Mapeamento dos campos flat da API → colunas Silver para vetos_detalhe
_FIELD_MAP_DETALHE: dict[str, tuple[str, type]] = {
    "Codigo": ("codigo", pl.Int64),
    "DataVotacao": ("data_votacao", pl.String),
    "Resultado": ("resultado", pl.String),
    "DescricaoResultado": ("descricao_resultado", pl.String),
    "TotalParlamentares": ("total_parlamentares", pl.Int64),
    "TotalSim": ("total_sim", pl.Int64),
    "TotalNao": ("total_nao", pl.Int64),
    "TotalAbstencao": ("total_abstencao", pl.Int64),
}


class VetosPresidenciaisTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de vetos presidenciais.

    O DataFrame de entrada contém campos flat (sem envelopes XML).
    O transformer renomeia para snake_case e aplica tipagem estrita.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma o DataFrame bruto de vetos presidenciais para o contrato Silver.

        Args:
            df: DataFrame bruto da API (colunas PascalCase).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme SILVER_SCHEMAS.
            Retorna DataFrame vazio se a entrada for vazia.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.VETOS_PRESIDENCIAIS.value]

        # ── Renomeia e tipa campos disponíveis ──────────────────────────────
        for api_name, (silver_col, _dtype) in _FIELD_MAP_PRESIDENCIAIS.items():
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                df = df.rename({api_name: silver_col})

        # ── Cast dos campos do contrato ─────────────────────────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])


class VetosDetalheTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de detalhes de veto.

    O DataFrame de entrada contém campos flat (sem envelopes XML).
    O transformer renomeia para snake_case e aplica tipagem estrita.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma o DataFrame bruto de detalhes de veto para o contrato Silver.

        Args:
            df: DataFrame bruto da API (colunas PascalCase).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme SILVER_SCHEMAS.
            Retorna DataFrame vazio se a entrada for vazia.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.VETOS_DETALHE.value]

        # ── Renomeia e tipa campos disponíveis ──────────────────────────────
        for api_name, (silver_col, _dtype) in _FIELD_MAP_DETALHE.items():
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                df = df.rename({api_name: silver_col})

        # ── Cast dos campos do contrato ─────────────────────────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
