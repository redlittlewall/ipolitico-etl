"""Transformador para o domínio SERVIDORES — desaninha roster do Senado.

Aplica o contrato Silver ao DataFrame bruto do extrator. O JSON tem 12 campos
com três aninhamentos — ``lotacao`` = {sigla, nome}, ``categoria`` = {codigo,
nome} e ``cedido`` = {tipo_cessao, orgao_origem, orgao_destino} — que são
achatados em colunas snake_case (mesmo conjunto de colunas do subpath CSV da
API). ``sequencial`` e ``nome`` são preservados: o join roster↔remuneração por
nome é downstream, não responsabilidade do ETL.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer
from ipolitico.transformers.senado.senadores_transformer import _struct_fields

# Aninhados → colunas Silver. ``cedido`` é nulo/ausente para servidores não
# cedidos; a extração guarda por struct (dtype Null) e o helper emite nulo.
_NESTED_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("lotacao", "lotacao_sigla", "sigla"),
    ("lotacao", "lotacao_nome", "nome"),
    ("categoria", "categoria_codigo", "codigo"),
    ("categoria", "categoria_nome", "nome"),
    ("cedido", "tipo_cessao", "tipo_cessao"),
    ("cedido", "orgao_origem", "orgao_origem"),
    ("cedido", "orgao_destino", "orgao_destino"),
)


def _struct_field(df: pl.DataFrame, struct_col: str, field_name: str) -> pl.Expr | None:
    """Retorna a expressão de um campo de struct, ou None se indisponível.

    Uma coluna de struct pode não existir (domínio sem o aninhado), não ser
    struct (dtype ``Null`` — todos os registros sem o objeto, ex: ``cedido``)
    ou não ter o campo pedido. Em qualquer caso devolve None, e o chamador
    emite nulo no lugar de quebrar a extração de campo.

    Args:
        df: DataFrame bruto (schema já inferido com ``infer_schema_length=None``).
        struct_col: Nome da coluna struct (ex: ``"cedido"``).
        field_name: Campo dentro do struct (ex: ``"tipo_cessao"``).

    Returns:
        Expressão Polars do campo, ou None quando o campo não está disponível.
    """
    if field_name not in _struct_fields(df, struct_col):
        return None
    return pl.col(struct_col).struct.field(field_name)


class SenadoServidoresTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto do roster de servidores.

    Desaninha ``lotacao``/``categoria``/``cedido`` em colunas snake_case,
    preserva os 9 campos top-level (com ``sequencial`` e ``nome`` intactos para
    o join downstream) e aplica a tipagem estrita do contrato Silver.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma o DataFrame bruto do roster em conformidade com o contrato.

        Args:
            df: DataFrame bruto do extrator (aninhamentos preservados,
                ``_source_url`` injetado).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame na ordem e tipagem exatas de ``SILVER_SCHEMAS[servidores]``.
            DataFrame vazio retorna vazio (sem colunas adicionadas).
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.SERVIDORES.value]

        # ── Desaninha os aninhados ─────────────────────────────────────────
        for struct_col, silver_col, field_name in _NESTED_FIELDS:
            if silver_col not in contract:
                continue
            expr = _struct_field(df, struct_col, field_name)
            if expr is not None:
                df = df.with_columns(expr.alias(silver_col))
            else:
                df = df.with_columns(pl.lit(None).alias(silver_col))

        # ── Campos top-level ausentes viram nulo (contrato exige a coluna) ──
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        # ── Seleção + cast estrito na ordem do contrato ────────────────────
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
