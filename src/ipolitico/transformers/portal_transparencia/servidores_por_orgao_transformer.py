"""Transformador para o domínio CG_SERVIDORES — agregado por órgão (API v3).

Aplica o contrato Silver ao DataFrame bruto da API v3 ``/servidores/por-orgao``
do Portal da Transparência (CGU). O contrato (validado real no ticket 03) tem 13
campos: contagens (``qntPessoas``/``qntVinculos``), dimensões por chave SK
(situação/tipo de vínculo/tipo de servidor, cada uma com descrição) e o órgão
SIAPE de exercício/superior (código String — preserva zeros à esquerda).

O snapshot não tem partição temporal: o transformer é o único lugar onde a
tipagem é travada (sem ``schema_overrides`` — a fonte é JSON da API, não CSV de
dump; a leitura raw do extrator já devolve os tipos nativos).
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer


class PortalServidoresPorOrgaoTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto do agregado por-orgao.

    Preserva as contagens (Int64) e as dimensões/órgãos (String — ``codOrgao*``
    guarda zeros à esquerda, ex: "081300") e aplica a tipagem estrita do
    contrato Silver na ordem exata de ``SILVER_SCHEMAS[cg_servidores]``.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da API em conformidade com o contrato.

        Args:
            df: DataFrame bruto do extrator (colunas da API v3 com
                ``_source_url`` injetado na extração).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[cg_servidores]``.
            DataFrame vazio retorna vazio (sem colunas adicionadas).
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_SERVIDORES.value]

        # ── Campos top-level ausentes viram nulo (contrato exige a coluna) ──
        # Um único with_columns vetorizado (nunca loops Python explícitos — ver
        # mesmo padrão no PortalRemuneracoesBulkTransformer).
        df = df.with_columns(
            [
                pl.lit(None).cast(contract[c]).alias(c)
                for c in contract
                if c not in df.columns
            ]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
