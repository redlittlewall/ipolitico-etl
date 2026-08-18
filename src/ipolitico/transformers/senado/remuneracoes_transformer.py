"""Transformador para o domínio REMUNERACOES — contrato Silver da folha do Senado.

Aplica o contrato Silver ao DataFrame bruto do extrator. O payload tem 20 campos
top-level (sem aninhamento): chave (``sequencial``, ``nome``, ``mes``, ``ano``,
``tipo_folha``) + 15 valores monetários em **string BR** (``"1.234,56"``,
``"-9.463,65"``) — convertidos para ``Float64`` via
``br_locale.convert_br_currency_columns``.

``sequencial`` e ``nome`` são preservados: o join roster↔remuneração por nome
(com validação de homônimos) é downstream, não responsabilidade do ETL.
``tipo_folha`` (``Normal`` + ``Suplementar``) é preservado — folha suplementar
é dado real.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer
from ipolitico.transformers.br_locale import convert_br_currency_columns

# 15 campos monetários do payload — string BR → Float64 (via br_locale).
_MONETARY_COLUMNS: tuple[str, ...] = (
    "remuneracao_basica",
    "vantagens_pessoais",
    "funcao_comissionada",
    "gratificacao_natalina",
    "horas_extras",
    "outras_eventuais",
    "abono_permanencia",
    "reversao_teto_constitucional",
    "imposto_renda",
    "previdencia",
    "faltas",
    "remuneracao_liquida",
    "diarias",
    "auxilios",
    "vantagens_indenizatorias",
)


class SenadoRemuneracoesTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto da folha mensal do Senado.

    Converte os 15 campos monetários de string BR para ``Float64``, preserva a
    chave (``sequencial``/``nome``/``mes``/``ano``/``tipo_folha``) e aplica a
    tipagem estrita do contrato Silver.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto da folha em conformidade com o contrato.

        Args:
            df: DataFrame bruto do extrator (valores monetários em string BR,
                ``_source_url`` injetado).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[remuneracoes]``.
            DataFrame vazio retorna vazio (sem colunas adicionadas).
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.REMUNERACOES.value]

        # ── Converte moeda BR (string → Float64) ─────────────────────────────
        # Colunas ausentes no DataFrame são ignoradas pelo helper (viram nulo
        # no passo seguinte; o cast estrito final fixa o dtype).
        df = convert_br_currency_columns(df, list(_MONETARY_COLUMNS))

        # ── Campos top-level ausentes viram nulo (contrato exige a coluna) ──
        # Uma única chamada vetorizada; sem loop imperativo sobre o DataFrame.
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
