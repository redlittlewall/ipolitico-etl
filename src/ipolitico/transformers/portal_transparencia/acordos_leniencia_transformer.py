"""Transformador para o domínio CG_ACORDOS_LENIENCIA — Acordos de Leniência (API v3).

O DTO da API v3 (``/api-de-dados/acordos-leniencia``) traz a lista ``sancoes``
contendo as empresas sancionadas vinculadas ao acordo (campos:
``nomeInformadoOrgaoResponsavel``, ``razaoSocial``, ``nomeFantasia``, ``cnpj``,
``cnpjFormatado``). O transformer explode a lista de empresas, achata os campos
de cada empresa, preenche colunas ausentes do contrato com nulo e aplica a
tipagem estrita de ``SILVER_SCHEMAS[cg_acordos_leniencia]``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

_SANCOES_FIELD_MAP = {
    "cnpj": "cnpjEmpresa",
    "cnpjFormatado": "cnpjFormatadoEmpresa",
    "razaoSocial": "razaoSocialEmpresa",
    "nomeFantasia": "nomeFantasiaEmpresa",
    "nomeInformadoOrgaoResponsavel": "nomeInformadoOrgaoResponsavel",
}


class PortalAcordosLenienciaTransformer(BaseTransformer):
    """Aplica o contrato Silver ao DataFrame bruto da API v3 de Acordos de Leniência."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da API em conformidade com o contrato Silver.

        Args:
            df: DataFrame bruto do extrator (lista de sanções aninhada, _source_url injetado).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[cg_acordos_leniencia]``.
            DataFrame vazio retorna vazio.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_ACORDOS_LENIENCIA.value]

        # ── Explode a lista de empresas sancionadas se presente ─────────────
        if "sancoes" in df.columns:
            if df.schema["sancoes"] == pl.List:
                df = df.explode("sancoes")

            if df.schema["sancoes"] == pl.Struct:
                struct_fields = {f.name for f in df.schema["sancoes"].fields}
                df = df.with_columns(
                    [
                        pl.col("sancoes").struct.field(src).alias(target)
                        for src, target in _SANCOES_FIELD_MAP.items()
                        if src in struct_fields
                    ]
                )
            df = df.drop("sancoes")

        # ── Campos top-level ausentes viram nulo ───────────────────────────
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
