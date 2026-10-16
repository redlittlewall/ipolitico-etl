"""Transformador para o domínio CG_CONVENIOS_ADITIVOS — Termos Aditivos de Convênios (API v3).

O DTO da API v3 (``/api-de-dados/convenios``) traz a relação de aditivos de
convênios celebrados pelo Governo Federal. O transformer padroniza os campos,
preenche colunas ausentes com nulos e aplica a tipagem estrita de
``SILVER_SCHEMAS[cg_convenios_aditivos]``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer


class PortalConveniosAditivosTransformer(BaseTransformer):
    """Aplica o contrato Silver ao DataFrame bruto da API v3 de aditivos de convênios."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da API em conformidade com o contrato Silver.

        Args:
            df: DataFrame bruto do extrator (_source_url injetado).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[cg_convenios_aditivos]``.
            DataFrame vazio retorna vazio.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_CONVENIOS_ADITIVOS.value]

        # Se o identificador veio como 'id' e 'idConvenio' não existe, renomeia
        if "id" in df.columns and "idConvenio" not in df.columns:
            df = df.rename({"id": "idConvenio"})

        # ── Campos top-level ausentes viram nulo ───────────────────────────
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
