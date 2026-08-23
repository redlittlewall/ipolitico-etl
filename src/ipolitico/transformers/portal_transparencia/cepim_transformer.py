"""Transformador para o domínio CG_CEPIM — Entidades Sem Fins Lucrativos Impedidas (API v3).

O DTO da API v3 (``/api-de-dados/cepim``) traz structs aninhadas (``orgaoSuperior``,
``pessoaJuridica``, ``convenio``). O transformer achata as structs em colunas
``<prefixo>_<campo>``, preenche colunas ausentes do contrato com nulo e aplica
a tipagem estrita de ``SILVER_SCHEMAS[cg_cepim]``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

_STRUCT_FLATTEN: dict[str, tuple[str, ...]] = {
    "orgaoSuperior": ("nome", "codigoSIAFI", "cnpj", "sigla", "descricaoPoder"),
    "pessoaJuridica": (
        "id",
        "cpfFormatado",
        "cnpjFormatado",
        "numeroInscricaoSocial",
        "nome",
        "razaoSocialReceita",
        "nomeFantasiaReceita",
        "tipo",
    ),
    "convenio": ("codigo", "objeto", "numero"),
}


class PortalCepimTransformer(BaseTransformer):
    """Aplica o contrato Silver ao DataFrame bruto da API v3 do CEPIM."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da API em conformidade com o contrato Silver.

        Args:
            df: DataFrame bruto do extrator (structs aninhadas, _source_url injetado).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[cg_cepim]``.
            DataFrame vazio retorna vazio.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_CEPIM.value]

        # ── Achata as structs do DTO em colunas do contrato ────────────────
        for struct_col, fields in _STRUCT_FLATTEN.items():
            if struct_col in df.columns and df.schema[struct_col] == pl.Struct:
                struct_field_names = {f.name for f in df.schema[struct_col].fields}
                df = df.with_columns(
                    [
                        pl.col(struct_col).struct.field(f).alias(f"{struct_col}_{f}")
                        for f in fields
                        if f in struct_field_names
                    ]
                )
        df = df.drop([c for c in _STRUCT_FLATTEN if c in df.columns])

        # ── Campos top-level ausentes viram nulo ───────────────────────────
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
