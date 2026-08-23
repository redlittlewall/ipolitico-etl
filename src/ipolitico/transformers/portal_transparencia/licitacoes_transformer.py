"""Transformador para o domínio CG_LICITACOES — Licitações do Executivo Federal (API v3).

O DTO da API v3 (``/api-de-dados/licitacoes``) traz structs aninhadas
(``licitacao``, ``municipio`` com sub-struct ``uf``, e ``unidadeGestora`` com
sub-structs ``orgaoVinculado`` e ``orgaoMaximo``). O transformer achata essas
estruturas hierárquicas em colunas normalizadas, preenche campos faltantes com
nulos e aplica a tipagem estrita de ``SILVER_SCHEMAS[cg_licitacoes]``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer


class PortalLicitacoesTransformer(BaseTransformer):
    """Aplica o contrato Silver ao DataFrame bruto da API v3 de licitações."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da API em conformidade com o contrato Silver.

        Args:
            df: DataFrame bruto do extrator (structs aninhadas, _source_url injetado).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[cg_licitacoes]``.
            DataFrame vazio retorna vazio.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_LICITACOES.value]

        # ── Achata licitacao ───────────────────────────────────────────────
        if "licitacao" in df.columns and df.schema["licitacao"] == pl.Struct:
            fields = {f.name for f in df.schema["licitacao"].fields}
            for f in ("numero", "objeto", "numeroProcesso", "contatoResponsavel"):
                if f in fields:
                    df = df.with_columns(pl.col("licitacao").struct.field(f).alias(f"licitacao_{f}"))
            df = df.drop("licitacao")

        # ── Achata municipio e sub-struct uf ────────────────────────────────
        if "municipio" in df.columns and df.schema["municipio"] == pl.Struct:
            mun_fields = {f.name for f in df.schema["municipio"].fields}
            for f in ("codigoIBGE", "nomeIBGE", "codigoRegiao", "nomeRegiao", "pais"):
                if f in mun_fields:
                    df = df.with_columns(pl.col("municipio").struct.field(f).alias(f"municipio_{f}"))
            if "uf" in mun_fields:
                df = df.with_columns([
                    pl.col("municipio").struct.field("uf").struct.field("sigla").alias("municipio_uf_sigla"),
                    pl.col("municipio").struct.field("uf").struct.field("nome").alias("municipio_uf_nome"),
                ])
            df = df.drop("municipio")

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

        # ── Campos top-level ausentes viram nulo ───────────────────────────
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
