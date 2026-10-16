"""Transformador para o domínio CG_CONTRATOS — Contratos do Executivo Federal (API v3).

O DTO da API v3 (``/api-de-dados/contratos``) traz structs aninhadas
(``compra``, ``unidadeGestora`` com sub-structs ``orgaoVinculado`` e
``orgaoMaximo``, ``unidadeGestoraCompras``, e ``fornecedor``). O transformer
achata essas estruturas em colunas normalizadas, preenche campos faltantes com
nulos e aplica a tipagem estrita de ``SILVER_SCHEMAS[cg_contratos]``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

_FORNECEDOR_FIELDS = (
    "id",
    "cpfFormatado",
    "cnpjFormatado",
    "numeroInscricaoSocial",
    "nome",
    "razaoSocialReceita",
    "nomeFantasiaReceita",
    "tipo",
)


class PortalContratosTransformer(BaseTransformer):
    """Aplica o contrato Silver ao DataFrame bruto da API v3 de contratos."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da API em conformidade com o contrato Silver.

        Args:
            df: DataFrame bruto do extrator (structs aninhadas, _source_url injetado).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[cg_contratos]``.
            DataFrame vazio retorna vazio.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_CONTRATOS.value]

        # ── Achata compra ──────────────────────────────────────────────────
        if "compra" in df.columns and df.schema["compra"] == pl.Struct:
            fields = {f.name for f in df.schema["compra"].fields}
            for f in ("numero", "objeto", "numeroProcesso", "contatoResponsavel"):
                if f in fields:
                    df = df.with_columns(pl.col("compra").struct.field(f).alias(f"compra_{f}"))
            df = df.drop("compra")

        # ── Achata unidadeGestora e sub-structs vinculadas ──────────────────
        if "unidadeGestora" in df.columns and df.schema["unidadeGestora"] == pl.Struct:
            ug_fields = {f.name for f in df.schema["unidadeGestora"].fields}
            for f in ("codigo", "nome", "descricaoPoder"):
                if f in ug_fields:
                    df = df.with_columns(pl.col("unidadeGestora").struct.field(f).alias(f"unidadeGestora_{f}"))

            if "orgaoVinculado" in ug_fields:
                df = df.with_columns([
                    pl.col("unidadeGestora").struct.field("orgaoVinculado").struct.field("codigoSIAFI").alias("unidadeGestora_orgaoVinculado_codigoSIAFI"),
                    pl.col("unidadeGestora").struct.field("orgaoVinculado").struct.field("nome").alias("unidadeGestora_orgaoVinculado_nome"),
                    pl.col("unidadeGestora").struct.field("orgaoVinculado").struct.field("sigla").alias("unidadeGestora_orgaoVinculado_sigla"),
                ])

            if "orgaoMaximo" in ug_fields:
                df = df.with_columns([
                    pl.col("unidadeGestora").struct.field("orgaoMaximo").struct.field("codigo").alias("unidadeGestora_orgaoMaximo_codigo"),
                    pl.col("unidadeGestora").struct.field("orgaoMaximo").struct.field("nome").alias("unidadeGestora_orgaoMaximo_nome"),
                    pl.col("unidadeGestora").struct.field("orgaoMaximo").struct.field("sigla").alias("unidadeGestora_orgaoMaximo_sigla"),
                ])
            df = df.drop("unidadeGestora")

        # ── Achata unidadeGestoraCompras ────────────────────────────────────
        if "unidadeGestoraCompras" in df.columns and df.schema["unidadeGestoraCompras"] == pl.Struct:
            ugc_fields = {f.name for f in df.schema["unidadeGestoraCompras"].fields}
            for f in ("codigo", "nome", "descricaoPoder"):
                if f in ugc_fields:
                    df = df.with_columns(pl.col("unidadeGestoraCompras").struct.field(f).alias(f"unidadeGestoraCompras_{f}"))
            df = df.drop("unidadeGestoraCompras")

        # ── Achata fornecedor ──────────────────────────────────────────────
        if "fornecedor" in df.columns and df.schema["fornecedor"] == pl.Struct:
            forn_fields = {f.name for f in df.schema["fornecedor"].fields}
            for f in _FORNECEDOR_FIELDS:
                if f in forn_fields:
                    df = df.with_columns(pl.col("fornecedor").struct.field(f).alias(f"fornecedor_{f}"))
            df = df.drop("fornecedor")

        # ── Campos top-level ausentes viram nulo ───────────────────────────
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
