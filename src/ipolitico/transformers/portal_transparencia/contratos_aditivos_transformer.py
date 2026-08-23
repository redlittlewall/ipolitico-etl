"""Transformador para o domínio CG_CONTRATOS_ADITIVOS — Termos Aditivos de Contratos (API v3).

O DTO da API v3 (``/api-de-dados/contratos/termo-aditivo``) traz a relação de termos
aditivos vinculados a contratos administrativos da União. O transformer padroniza
as colunas, preenche campos faltantes com nulos e aplica a tipagem estrita de
``SILVER_SCHEMAS[cg_contratos_aditivos]``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer


class PortalContratosAditivosTransformer(BaseTransformer):
    """Aplica o contrato Silver ao DataFrame bruto da API v3 de termos aditivos."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da API em conformidade com o contrato Silver.

        Args:
            df: DataFrame bruto do extrator (_source_url injetado).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[cg_contratos_aditivos]``.
            DataFrame vazio retorna vazio.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_CONTRATOS_ADITIVOS.value]

        # Se o identificador veio como 'id' e 'idContrato' não existe, renomeia
        if "id" in df.columns and "idContrato" not in df.columns:
            df = df.rename({"id": "idContrato"})

        # ── Campos top-level ausentes viram nulo ───────────────────────────
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
