"""Transformador para o domínio CG_PEP — contrato Silver provisório (API v3).

**Contrato PROVISIONAL** (mesmo status de cg_remuneracoes no ticket 03): o dump
bulk ``pep`` está indisponível (403/AccessDenied no host de dumps — validado
real no ticket 04), então o shape é derivado do JSON real da API v3
(``/api-de-dados/peps`` — "Pessoas Expostas Politicamente"). A validação reabre
quando o dump publicar.

Fatos do DTO real (validados): campos já em **snake_case idênticos ao contrato**
(1:1, sem rename); ``nome``/``sigla_funcao``/``nome_orgao`` com **padding fixo
de espaços à direita** (``str.strip``); ``nivel_funcao`` com zeros à esquerda
(``"005"`` — String, não numérico); ``cod_orgao`` pode ser ``"CGUSIAPE"``
(não-numérico); CPF mascarado (``"***.848.518-**"``); datas ISO ``"YYYY-MM-DD"``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer


class PortalPepTransformer(BaseTransformer):
    """Aplica o contrato Silver (provisório) ao DataFrame bruto da API de peps.

    Remove o padding fixo de espaços dos campos String (``nome``,
    ``sigla_funcao``, ``nome_orgao`` — formato real do DTO), preenche colunas
    do contrato ausentes com nulo e aplica a tipagem estrita de
    ``SILVER_SCHEMAS[cg_pep]``.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da API em conformidade com o contrato.

        Args:
            df: DataFrame bruto do extrator (DTO já em snake_case do contrato,
                ``_source_url`` injetado, campos String com padding de espaços).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[cg_pep]``.
            DataFrame vazio retorna vazio (sem colunas adicionadas).
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_PEP.value]

        # ── Remove o padding fixo de espaços dos campos String reais ────────
        # ``_source_url`` preservado; demais colunas String do contrato são
        # limpas (``nome``/``sigla_funcao``/``nome_orgao`` têm espaços à
        # direita no DTO; os demais campos não são afetados pelo strip).
        strip_cols = [c for c in contract if c != "_source_url" and c in df.columns]
        if strip_cols:
            df = df.with_columns([pl.col(c).str.strip_chars().alias(c) for c in strip_cols])

        # ── Campos top-level ausentes viram nulo (contrato exige a coluna) ──
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
