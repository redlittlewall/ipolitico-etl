"""Transformador para o domínio CG_IMOVEIS_FUNCIONAIS — API v3 (shape confirmado).

O DTO real da API v3 (``/api-de-dados/imoveis``) traz ``orgaoResponsavel``,
``situacao`` e ``regiao`` como structs aninhadas. O transformer achata cada
struct em colunas ``<prefixo>_<campo>`` do contrato (ex:
``orgaoResponsavel.nome`` → ``orgaoResponsavel_nome``), preenche colunas do
contrato ausentes com nulo e aplica a tipagem estrita de
``SILVER_SCHEMAS[cg_imoveis_funcionais]``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

# Mapeamento struct do DTO → prefixo das colunas achatadas no contrato. Cada
# campo da struct vira ``<prefixo>_<campo>`` (ex: ``regiao.id`` →
# ``regiao_id``). Campos ausentes numa resposta são ignorados (viram nulo).
_STRUCT_FLATTEN: dict[str, tuple[str, ...]] = {
    "orgaoResponsavel": ("nome", "codigoSIAFI"),
    "situacao": ("id", "descricao"),
    "regiao": ("id", "descricao"),
}


class PortalImoveisFuncionaisTransformer(BaseTransformer):
    """Aplica o contrato Silver ao DataFrame bruto da API v3 de imóveis funcionais.

    Achata as structs ``orgaoResponsavel``/``situacao``/``regiao`` do DTO em
    colunas ``<prefixo>_<campo>``, preenche colunas ausentes com nulo e aplica
    a tipagem estrita do contrato Silver.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da API em conformidade com o contrato.

        Args:
            df: DataFrame bruto do extrator (structs aninhadas, ``_source_url``
                injetado como primeira coluna).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de
            ``SILVER_SCHEMAS[cg_imoveis_funcionais]``. DataFrame vazio retorna
            vazio (sem colunas adicionadas).
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_IMOVEIS_FUNCIONAIS.value]

        # ── Achata as structs do DTO em colunas do contrato ────────────────
        # A struct pode vir com dtype Null quando todos os valores são nulos
        # numa página; o guard evita acessar o namespace ``struct`` sem base.
        for struct_col, fields in _STRUCT_FLATTEN.items():
            if struct_col not in df.columns or df.schema[struct_col] != pl.Struct:
                continue
            struct_field_names = {f.name for f in df.schema[struct_col].fields}
            df = df.with_columns(
                [
                    pl.col(struct_col).struct.field(f).alias(f"{struct_col}_{f}")
                    for f in fields
                    if f in struct_field_names
                ]
            )
        df = df.drop([c for c in _STRUCT_FLATTEN if c in df.columns])

        # ── Campos top-level ausentes viram nulo (contrato exige a coluna) ──
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
