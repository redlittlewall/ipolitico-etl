"""Transformador para o domínio SENADORES — aplaina envelope XML-heritage."""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer


def _struct_fields(df: pl.DataFrame, col: str) -> set[str]:
    """Retorna nomes de campos disponíveis em uma coluna struct."""
    dtype = df.schema.get(col)
    if dtype is None:
        return set()
    fields = getattr(dtype, "fields", None)
    if fields is None:
        return set()
    return {f.name for f in fields}


class SenadoSenadoresTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de senadores.

    O DataFrame de entrada tem colunas aninhadas:
    - ``IdentificacaoParlamentar`` (struct) com dados cadastrais
    - ``Mandatos`` (struct) com ``Mandato`` (list de structs)

    O transformer extrai campos dos envelopes, renomeia para snake_case
    e aplica a tipagem estrita do contrato Silver.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.SENADORES.value]
        available_id = _struct_fields(df, "IdentificacaoParlamentar")

        # ── Extrai campos de IdentificacaoParlamentar ──────────────────────
        id_struct = pl.col("IdentificacaoParlamentar")
        for api_name, silver_col, dtype in [
            ("CodigoParlamentar", "codigo", pl.Int64),
            ("NomeParlamentar", "nome", pl.String),
            ("NomeCompletoParlamentar", "nome_completo", pl.String),
            ("SexoParlamentar", "sexo", pl.String),
        ]:
            if silver_col not in contract:
                continue
            if api_name in available_id:
                expr = id_struct.struct.field(api_name)
                if dtype == pl.Int64:
                    expr = expr.cast(pl.Int64)
                df = df.with_columns(expr.alias(silver_col))
            else:
                df = df.with_columns(pl.lit(None).alias(silver_col))

        # ── Extrai campos do primeiro mandato ──────────────────────────────
        primeiro_mandato = pl.col("Mandatos").struct.field("Mandato").list.first()
        available_mandato = _mandato_fields(df)

        for api_name, silver_col, dtype in [
            ("UfParlamentar", "uf", pl.String),
            ("CodigoMandato", "codigo_mandato", pl.Int64),
            ("DescricaoParticipacao", "descricao_participacao", pl.String),
        ]:
            if silver_col not in contract:
                continue
            if api_name in available_mandato:
                expr = primeiro_mandato.struct.field(api_name)
                if dtype == pl.Int64:
                    expr = expr.cast(pl.Int64)
                df = df.with_columns(expr.alias(silver_col))
            else:
                df = df.with_columns(pl.lit(None).alias(silver_col))

        # ── Primeira/Segunda legislatura (dentro de sub-struct do mandato) ──
        for leg_key, silver_col in [
            ("PrimeiraLegislaturaDoMandato", "primeira_legislatura"),
            ("SegundaLegislaturaDoMandato", "segunda_legislatura"),
        ]:
            if silver_col not in contract:
                continue
            if leg_key in available_mandato:
                sub_available = _mandato_sub_fields(df, leg_key)
                if "NumeroLegislatura" in sub_available:
                    df = df.with_columns(
                        primeiro_mandato.struct.field(leg_key)
                        .struct.field("NumeroLegislatura")
                        .cast(pl.Int64)
                        .alias(silver_col)
                    )
                else:
                    df = df.with_columns(pl.lit(None).alias(silver_col))
            else:
                df = df.with_columns(pl.lit(None).alias(silver_col))

        # ── Aplica contrato Silver (seleção + cast estrito) ─────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])


def _mandato_fields(df: pl.DataFrame) -> set[str]:
    """Retorna nomes de campos disponíveis no struct do primeiro mandato."""
    mandatos_dtype = df.schema.get("Mandatos")
    if mandatos_dtype is None:
        return set()
    for f in getattr(mandatos_dtype, "fields", ()):
        if f.name == "Mandato":
            inner = getattr(f.dtype, "inner", None)
            if inner is not None and hasattr(inner, "fields"):
                return {sf.name for sf in inner.fields}
    return set()


def _mandato_sub_fields(df: pl.DataFrame, leg_key: str) -> set[str]:
    """Retorna nomes de campos de uma sub-estrutura de legislatura."""
    mandatos_dtype = df.schema.get("Mandatos")
    if mandatos_dtype is None:
        return set()
    for f in getattr(mandatos_dtype, "fields", ()):
        if f.name == "Mandato":
            inner = getattr(f.dtype, "inner", None)
            if inner is not None and hasattr(inner, "fields"):
                for sf in inner.fields:
                    if sf.name == leg_key and hasattr(sf.dtype, "fields"):
                        return {ssf.name for ssf in sf.dtype.fields}
    return set()
