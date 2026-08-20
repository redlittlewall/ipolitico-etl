"""Transformador do domínio CG_VIAGENS — contrato Silver do CSV real capturado.

Aplica o contrato Silver ao DataFrame bruto do dump anual de viagens (Portal da
Transparência — CGU). A renomeação das 22 colunas do CSV (latin-1, ponto-e-
vírgula) para o snake_case do contrato NÃO vive aqui: é o ``rename_map`` do
``BULK_REGISTRY[cg_viagens]``, aplicado no ``_read_single_csv`` do extrator —
o transformer recebe colunas já nomeadas pelo contrato (``_source_url`` como
primeira coluna, valores ainda como string crua).

O que o transformer faz:

1. **Moeda BR → Float64**: ``valor_diarias``/``valor_passagens``/
   ``valor_devolucao``/``valor_outros_gastos`` vêm como string vírgula-decimal
   (``"8791,50"``) → ``convert_br_currency_columns``.
2. **Sentinels → nulo** (ausência, mesmo padrão dos demais domínios do portal):
   ``funcao ∈ {"-1", "-11"}`` (99,9% das 855.805 linhas do dump real de 2016 —
   códigos de "Sem informação" e "Sigiloso": a função do viajante quase nunca
   é pública) e strings vazias em qualquer coluna String. A linha é: códigos
   de ausência (``-1``/``-11``) e strings vazias → nulo; texto legível de
   status ("Informações protegidas por sigilo…", "Sem informação") permanece
   como valor — é o status real da linha, não um código.
3. **Contrato estrito**: colunas ausentes viram nulo e o resultado é selecionado
   na ordem/tipagem exatas de ``SILVER_SCHEMAS[cg_viagens]``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer
from ipolitico.transformers.br_locale import convert_br_currency_columns

# Campos monetários do contrato — string BR vírgula-decimal → Float64 (via
# br_locale). Lista fixa no código (mesmo padrão do Senado/CG_REMUNERACOES):
# colunas ausentes no DataFrame são ignoradas pelo helper e viram nulo em
# seguida.
_MONETARY_COLUMNS: tuple[str, ...] = (
    "valor_diarias",
    "valor_passagens",
    "valor_devolucao",
    "valor_outros_gastos",
)


class PortalViagensTransformer(BaseTransformer):
    """Aplica o contrato Silver ao DataFrame bruto do dump anual de viagens.

    Converte os 4 campos monetários de string BR para ``Float64``, normaliza
    sentinels reais (``funcao = "-11"`` e strings vazias → nulo), preenche
    colunas do contrato ausentes no dump com nulo e aplica a tipagem estrita
    do contrato Silver.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto do dump em conformidade com o contrato.

        Args:
            df: DataFrame bruto do ``PortalViagensBulkExtractor`` (colunas já
                renomeadas pelo ``rename_map`` do registry, ``_source_url``
                como primeira coluna, valores de moeda em string BR).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de
            ``SILVER_SCHEMAS[cg_viagens]``. DataFrame vazio retorna vazio.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_VIAGENS.value]

        # ── Moeda BR (string "8.791,50" → Float64) ───────────────────────────
        df = convert_br_currency_columns(df, list(_MONETARY_COLUMNS))

        # ── Sentinels → nulo: strings vazias e códigos de ausência de função ──
        # Em 2016, 99,9% das linhas têm funcao "-1" (Sem informação) ou "-11"
        # (Sigiloso) — a função do viajante quase nunca é pública. Códigos de
        # ausência e strings vazias → nulo (mesmo padrão dos sentinels "-1"/"-3"
        # da API). Texto legível ("Informações protegidas por sigilo…", "Sem
        # informação") permanece: é o status real da linha, não um código.
        df = df.with_columns(
            [
                pl.when(pl.col(c) == "").then(pl.lit(None)).otherwise(pl.col(c)).alias(c)
                for c in df.columns
                if df.schema[c] == pl.String and c != "_source_url"
            ]
        )
        if "funcao" in df.columns:
            df = df.with_columns(
                pl.when(pl.col("funcao").is_in(["-1", "-11"]))
                .then(pl.lit(None))
                .otherwise(pl.col("funcao"))
                .alias("funcao")
            )

        # ── Campos do contrato ausentes no dump viram nulo ─────────────────
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
