"""Transformador para o domínio DESPESAS_CEAPS — contrato Silver do CEAP do Senado.

Aplica o contrato Silver ao DataFrame bruto do extrator. O payload tem 13 campos
top-level (sem aninhamento): ``id``, ``tipoDocumento``, ``ano``, ``mes``,
``codSenador``, ``nomeSenador``, ``tipoDespesa``, ``cpfCnpj``, ``fornecedor``,
``documento``, ``data``, ``detalhamento``, ``valorReembolsado``.

``valorReembolsado`` vem como **número** (float/int) na API real, mas o survey
documenta o formato **string BR** (``"1.234,56"``) — o transformer converte
ambos para ``Float64`` via ``br_locale.convert_br_currency_columns`` (string
converte, número passa direto pelo cast).

``codSenador``/``nomeSenador`` são preservados: o join com o roster (por
``codigoParlamentar``) é downstream, não responsabilidade do ETL. ``data`` é
ISO string (``"2025-09-26"``) preservada — campos documentais podem ser nulos
em anos antigos (ex: 2008), o cast estrito os mantém como nulo.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer
from ipolitico.transformers.br_locale import convert_br_currency_columns

# Único campo monetário do payload — número ou string BR → Float64.
_MONETARY_COLUMNS: tuple[str, ...] = ("valorReembolsado",)


class SenadoDespesasCeapsTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto das despesas CEAP do Senado.

    Converte ``valorReembolsado`` para ``Float64`` (número passa direto; string
    BR converte via ``br_locale``), preserva as chaves (``id``, ``codSenador``,
    ``nomeSenador``, ``ano``/``mes``) e aplica a tipagem estrita do contrato.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto das despesas em conformidade com o contrato.

        Args:
            df: DataFrame bruto do extrator (``valorReembolsado`` como número ou
                string BR, ``_source_url`` injetado).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[despesas_ceaps]``.
            DataFrame vazio retorna vazio (sem colunas adicionadas).
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.DESPESAS_CEAPS.value]

        # ── Converte moeda (string BR → Float64; número passa direto) ────────
        df = convert_br_currency_columns(df, list(_MONETARY_COLUMNS))

        # ── Campos top-level ausentes viram nulo (contrato exige a coluna) ──
        # Uma única chamada vetorizada; sem loop imperativo sobre o DataFrame.
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
