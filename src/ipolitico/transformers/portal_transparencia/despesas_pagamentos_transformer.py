"""Transformador para o domínio CG_DESPESAS_PAGAMENTOS — Documentos de Pagamento (API v3).

O DTO da API v3 (``/api-de-dados/despesas/documentos``) traz dados da ordem bancária
ou documento de pagamento (fase 3). O transformer converte a coluna ``valor`` em
formato brasileiro ('1.234,56') para ``Float64`` através de
``convert_br_currency_columns``, preenche colunas ausentes com nulos e aplica a
tipagem estrita de ``SILVER_SCHEMAS[cg_despesas_pagamentos]``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer
from ipolitico.transformers.br_locale import convert_br_currency_columns


class PortalDespesasPagamentosTransformer(BaseTransformer):
    """Aplica o contrato Silver ao DataFrame bruto da API v3 de pagamentos de despesas."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da API em conformidade com o contrato Silver.

        Args:
            df: DataFrame bruto do extrator (_source_url injetado).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[cg_despesas_pagamentos]``.
            DataFrame vazio retorna vazio.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_DESPESAS_PAGAMENTOS.value]

        # Converte coluna monetária em formato BR
        if "valor" in df.columns:
            df = convert_br_currency_columns(df, ["valor"])

        # ── Campos top-level ausentes viram nulo ───────────────────────────
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
