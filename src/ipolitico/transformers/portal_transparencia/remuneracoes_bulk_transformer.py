"""Transformador para o domínio CG_REMUNERACOES — contrato Silver provisório.

Aplica o contrato Silver ao DataFrame bruto do dump mensal do Portal da
Transparência (CGU). **Contrato PROVISIONAL**: a validação real do ticket 03
bloqueou o download pelo WAF/CAPTCHA do host de dumps, então a renomeação real
das colunas do CSV ainda não foi travada — quando o WAF liberar, o ticket
reabre para validar os nomes de origem.

O que já está garantido pelo contrato:

1. **Compatibilidade retroativa pré-2020**: a folha do Executivo passou a
   publicar o detalhe completo de rubricas em 2020. Fixtures pré-2020 omitem
   esses campos → viram nulo (o transformer preenche colunas ausentes do
   contrato com nulo, mesmo padrão do ``SenadoRemuneracoesTransformer``).
2. **Moeda BR**: valores monetários vêm em string BR (``"12.000,00"``) →
   ``Float64`` via ``convert_br_currency_columns``.
3. **Identidade preservada**: ``id_servidor``, ``nome``, ``cpf``, ``matricula``,
   órgãos de lotação/exercício e ``mes_ano`` (String — join downstream).
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer
from ipolitico.transformers.br_locale import convert_br_currency_columns

# Campos monetários do contrato — string BR → Float64 (via br_locale). Lista
# fixa no código (mesmo padrão do Senado): colunas ausentes no DataFrame são
# ignoradas pelo helper e viram nulo no passo seguinte.
_MONETARY_COLUMNS: tuple[str, ...] = (
    "remuneracao_basica",
    "gratificacao_natalina",
    "ferias",
    "outras_remuneracoes_eventuais",
    "imposto_retido_na_fonte",
    "previdencia_oficial",
    "outras_deducoes_obrigatorias",
    "pensao_militar",
    "fundo_saude",
    "taxa_ocupacao_imovel_funcional",
    "verbas_indenizatorias",
    "verbas_indenizatorias_civil",
    "verbas_indenizatorias_militar",
    "verbas_indenizatorias_referentes_pdv",
    "remuneracao_apos_deducoes",
)


class PortalRemuneracoesBulkTransformer(BaseTransformer):
    """Aplica contrato Silver (provisório) ao DataFrame bruto do dump mensal.

    Converte os campos monetários de string BR para ``Float64``, preenche
    colunas do contrato ausentes no dump (ex: rubricas pós-2020 em fixtures
    pré-2020) com nulo e aplica a tipagem estrita do contrato Silver.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto do dump em conformidade com o contrato.

        Args:
            df: DataFrame bruto do extrator (valores monetários em string BR,
                ``_source_url`` injetado, CSV lido com infer_schema_length=0).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de
            ``SILVER_SCHEMAS[cg_remuneracoes]``. DataFrame vazio retorna vazio
            (sem colunas adicionadas).
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.CG_REMUNERACOES.value]

        # ── Converte moeda BR (string → Float64) ─────────────────────────────
        # Colunas ausentes no DataFrame são ignoradas pelo helper (viram nulo
        # no passo seguinte; o cast estrito final fixa o dtype).
        df = convert_br_currency_columns(df, list(_MONETARY_COLUMNS))

        # ── Campos top-level ausentes viram nulo (contrato exige a coluna) ──
        df = df.with_columns(
            [pl.lit(None).cast(contract[c]).alias(c) for c in contract if c not in df.columns]
        )

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
