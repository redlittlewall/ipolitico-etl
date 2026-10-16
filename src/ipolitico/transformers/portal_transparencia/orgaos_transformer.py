"""Transformador para o domínio CG_ORGAOS — snapshot de órgãos do SIAPE.

Aplica o contrato Silver ao DataFrame bruto da API v3 ``/api-de-dados/
orgaos-siape`` do Portal da Transparência (CGU). A validação real do ticket 02
corrigiu a fonte: NÃO existe módulo bulk de órgãos no portal (o ticket assumia
``/download-de-dados/orgaos``), então o domínio vem da API v3 — o contrato é o
par ``codigo`` (String, preserva zeros à esquerda) / ``descricao``.

O snapshot não tem partição temporal: o transformer é o único lugar onde a
tipagem é travada (sem ``schema_overrides`` — a fonte é JSON da API, não CSV
de dump; a leitura raw do ``PortalOrgaosApiExtractor`` já devolve String).
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer


class PortalOrgaosTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto da API v3 de órgãos (SIAPE).

    Preserva as colunas nativas da API (``codigo``/``descricao`` como String —
    ``codigo`` guarda zeros à esquerda, ex: "00001") e aplica a tipagem estrita
    do contrato Silver na ordem exata de ``SILVER_SCHEMAS[cg_orgaos]``.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da API em conformidade com o contrato.

        Args:
            df: DataFrame bruto do extrator (colunas da API v3 com
                ``_source_url`` injetado na extração).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[cg_orgaos]``.
            DataFrame vazio retorna vazio (sem colunas adicionadas).
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_ORGAOS.value]

        # ── Campos top-level ausentes viram nulo (contrato exige a coluna) ──
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
