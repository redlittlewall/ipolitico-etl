"""Transformador para o domínio CG_CONVENIOS — Convênios e Transferências Voluntárias (API v3).

O DTO da API v3 (``/api-de-dados/convenios``) traz structs aninhadas
(``dimConvenio``, ``convenente``, ``municipioConvenente`` com sub-struct ``uf``,
``orgao``, ``unidadeGestora``, ``tipoInstrumento``). O transformer achata essas
estruturas em colunas normalizadas, preenche campos faltantes com nulos e aplica
a tipagem estrita de ``SILVER_SCHEMAS[cg_convenios]``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

_CONVENENTE_FIELDS = (
    "id",
    "cpfFormatado",
    "cnpjFormatado",
    "numeroInscricaoSocial",
    "nome",
    "razaoSocialReceita",
    "nomeFantasiaReceita",
    "tipo",
)


class PortalConveniosTransformer(BaseTransformer):
    """Aplica o contrato Silver ao DataFrame bruto da API v3 de convênios."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da API em conformidade com o contrato Silver.

        Args:
            df: DataFrame bruto do extrator (structs aninhadas, _source_url injetado).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[cg_convenios]``.
            DataFrame vazio retorna vazio.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_CONVENIOS.value]

        # ── Achata dimConvenio ─────────────────────────────────────────────
        if "dimConvenio" in df.columns and df.schema["dimConvenio"] == pl.Struct:
            fields = {f.name for f in df.schema["dimConvenio"].fields}
            for f in ("codigo", "objeto", "numero"):
                if f in fields:
                    df = df.with_columns(pl.col("dimConvenio").struct.field(f).alias(f"dimConvenio_{f}"))
            df = df.drop("dimConvenio")

        # ── Achata convenente ──────────────────────────────────────────────
        if "convenente" in df.columns and df.schema["convenente"] == pl.Struct:
            fields = {f.name for f in df.schema["convenente"].fields}
            for f in _CONVENENTE_FIELDS:
                if f in fields:
                    df = df.with_columns(pl.col("convenente").struct.field(f).alias(f"convenente_{f}"))
            df = df.drop("convenente")

        # ── Achata municipioConvenente e sub-struct uf ──────────────────────
        if "municipioConvenente" in df.columns and df.schema["municipioConvenente"] == pl.Struct:
            mun_fields = {f.name for f in df.schema["municipioConvenente"].fields}
            for f in ("codigoIBGE", "nomeIBGE", "codigoRegiao", "nomeRegiao", "pais"):
                if f in mun_fields:
                    df = df.with_columns(pl.col("municipioConvenente").struct.field(f).alias(f"municipioConvenente_{f}"))
            if "uf" in mun_fields:
                df = df.with_columns([
                    pl.col("municipioConvenente").struct.field("uf").struct.field("sigla").alias("municipioConvenente_uf_sigla"),
                    pl.col("municipioConvenente").struct.field("uf").struct.field("nome").alias("municipioConvenente_uf_nome"),
                ])
            df = df.drop("municipioConvenente")

        # ── Achata orgao ───────────────────────────────────────────────────
        if "orgao" in df.columns and df.schema["orgao"] == pl.Struct:
            fields = {f.name for f in df.schema["orgao"].fields}
            for f in ("codigoSIAFI", "nome", "cnpj", "sigla", "descricaoPoder"):
                if f in fields:
                    df = df.with_columns(pl.col("orgao").struct.field(f).alias(f"orgao_{f}"))
            df = df.drop("orgao")

        # ── Achata unidadeGestora ──────────────────────────────────────────
        if "unidadeGestora" in df.columns and df.schema["unidadeGestora"] == pl.Struct:
            fields = {f.name for f in df.schema["unidadeGestora"].fields}
            for f in ("codigo", "nome", "descricaoPoder"):
                if f in fields:
                    df = df.with_columns(pl.col("unidadeGestora").struct.field(f).alias(f"unidadeGestora_{f}"))
            df = df.drop("unidadeGestora")

        # ── Achata tipoInstrumento ─────────────────────────────────────────
        if "tipoInstrumento" in df.columns and df.schema["tipoInstrumento"] == pl.Struct:
            fields = {f.name for f in df.schema["tipoInstrumento"].fields}
            for f in ("codigo", "descricao"):
                if f in fields:
                    df = df.with_columns(pl.col("tipoInstrumento").struct.field(f).alias(f"tipoInstrumento_{f}"))
            df = df.drop("tipoInstrumento")

        # ── Campos top-level ausentes viram nulo ───────────────────────────
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
