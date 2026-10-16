"""Transformador para o domínio CG_EMENDAS — API v3 (shape confirmado).

O DTO real da API v3 (``/api-de-dados/emendas``) é flat: campos top-level com
``valor*`` em string de moeda brasileira (``"64.172,10"``) e ``ano`` como
inteiro. O transformer converte os 6 campos monetários para ``Float64`` via
``convert_br_currency_columns``, preenche colunas do contrato ausentes com
nulo e aplica a tipagem estrita de ``SILVER_SCHEMAS[cg_emendas]``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer
from ipolitico.transformers.br_locale import convert_br_currency_columns

# Campos monetários do contrato — string BR → Float64 (via br_locale).
_MONETARY_COLUMNS: tuple[str, ...] = (
    "valorEmpenhado",
    "valorLiquidado",
    "valorPago",
    "valorRestoInscrito",
    "valorRestoCancelado",
    "valorRestoPago",
)


class PortalEmendasTransformer(BaseTransformer):
    """Aplica o contrato Silver ao DataFrame bruto da API v3 de emendas.

    Converte os 6 campos monetários de string BR para ``Float64``, preenche
    colunas do contrato ausentes na resposta com nulo e aplica a tipagem
    estrita do contrato Silver.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da API em conformidade com o contrato.

        Args:
            df: DataFrame bruto do extrator (DTO flat, ``_source_url`` injetado,
                valores monetários em string BR).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de
            ``SILVER_SCHEMAS[cg_emendas]``. DataFrame vazio retorna vazio
            (sem colunas adicionadas).
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_EMENDAS.value]

        # ── Converte moeda BR (string → Float64) ─────────────────────────────
        # Colunas ausentes são ignoradas pelo helper (viram nulo no passo
        # seguinte; o cast estrito final fixa o dtype).
        df = convert_br_currency_columns(df, list(_MONETARY_COLUMNS))

        # ── Campos top-level ausentes viram nulo (contrato exige a coluna) ──
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
