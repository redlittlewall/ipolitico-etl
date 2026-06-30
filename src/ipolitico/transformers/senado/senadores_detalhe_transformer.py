"""Transformador para o domínio SENADORES_DETALHE — aplaina detalhe do senador."""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer
from ipolitico.transformers.senado.senadores_transformer import _struct_fields


class SenadoSenadoresDetalheTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de detalhes de senadores.

    O DataFrame de entrada tem colunas aninhadas:
    - ``IdentificacaoParlamentar`` (struct) — codigo, nome, email, fotos
    - ``DadosBasicosParlamentar`` (struct) — data_nascimento, naturalidade

    O transformer extrai campos desses envelopes, renomeia para snake_case
    e aplica a tipagem estrita do contrato Silver.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.SENADORES_DETALHE.value]
        available_id = _struct_fields(df, "IdentificacaoParlamentar")
        available_basicos = _struct_fields(df, "DadosBasicosParlamentar")

        # ── Extrai campos de IdentificacaoParlamentar ──────────────────────
        id_struct = pl.col("IdentificacaoParlamentar")
        for api_name, silver_col, dtype in [
            ("CodigoParlamentar", "codigo", pl.Int64),
            ("NomeParlamentar", "nome", pl.String),
            ("NomeCompletoParlamentar", "nome_completo", pl.String),
            ("SexoParlamentar", "sexo", pl.String),
            ("UrlFotoParlamentar", "url_foto", pl.String),
            ("UrlPaginaParlamentar", "url_pagina", pl.String),
            ("EmailParlamentar", "email", pl.String),
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

        # ── Extrai campos de DadosBasicosParlamentar ───────────────────────
        basicos_struct = pl.col("DadosBasicosParlamentar")
        for api_name, silver_col in [
            ("DataNascimento", "data_nascimento"),
            ("Naturalidade", "naturalidade"),
            ("UfNaturalidade", "uf_naturalidade"),
        ]:
            if silver_col not in contract:
                continue
            if api_name in available_basicos:
                df = df.with_columns(basicos_struct.struct.field(api_name).alias(silver_col))
            else:
                df = df.with_columns(pl.lit(None).alias(silver_col))

        # ── Aplica contrato Silver (seleção + cast estrito) ─────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
