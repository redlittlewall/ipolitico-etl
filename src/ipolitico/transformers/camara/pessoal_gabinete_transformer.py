"""Transformer responsável pela normalização dos dados de Pessoal de Gabinete da Câmara."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


class CamaraPessoalGabineteTransformer(BaseTransformer):
    """
    Normalizador e validador de contrato Silver para Pessoal de Gabinete da Câmara.

    Aplica limpeza e padronização vetorizada sobre os nomes dos assessores (trim,
    uppercase e redução de múltiplos espaços em branco), conversão de datas de
    exercício para o tipo pl.Date e garante tipagem e ordenação estritas conforme
    definido em `SILVER_SCHEMAS[DomainType.CAMARA_GABINETE_ASSESSORES]`.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Executa a transformação e validação do contrato Silver para pessoal de gabinete.

        Args:
            df: DataFrame Polars bruto proveniente do extrator/scraper.
            **kwargs: Metadados contextuais adicionais (ignorados).

        Returns:
            pl.DataFrame: DataFrame normalizado, com tipagem e ordenação idênticas
                ao contrato da camada Silver. Retorna DataFrame vazio compatível
                caso a entrada esteja vazia.
        """
        contract = SILVER_SCHEMAS[DomainType.CAMARA_GABINETE_ASSESSORES.value]

        if df.is_empty():
            return pl.DataFrame(schema=contract)

        # Adiciona colunas ausentes como null antes da transformação vetorizada
        for col, dtype in contract.items():
            if col not in df.columns:
                df = df.with_columns(pl.lit(None, dtype=dtype).alias(col))

        # 1. Normalização vetorizada de texto (nome, cargo, grupo funcional)
        df = df.with_columns(
            [
                pl.col("nome_assessor")
                .cast(pl.String, strict=False)
                .str.strip_chars()
                .str.replace_all(r"\s+", " ")
                .str.to_uppercase()
                .alias("nome_assessor"),
                pl.col("cargo")
                .cast(pl.String, strict=False)
                .str.strip_chars()
                .str.replace_all(r"\s+", " ")
                .alias("cargo"),
                pl.col("grupo_funcional")
                .cast(pl.String, strict=False)
                .str.strip_chars()
                .str.replace_all(r"\s+", " ")
                .alias("grupo_funcional"),
            ]
        )

        # 2. Conversão vetorizada de data_exercicio para pl.Date (DD/MM/YYYY e ISO YYYY-MM-DD)
        if df.schema.get("data_exercicio") != pl.Date:
            parsed_date = pl.coalesce(
                [
                    pl.col("data_exercicio")
                    .cast(pl.String, strict=False)
                    .str.to_date("%d/%m/%Y", strict=False),
                    pl.col("data_exercicio")
                    .cast(pl.String, strict=False)
                    .str.to_date("%Y-%m-%d", strict=False),
                ]
            )
            df = df.with_columns(parsed_date.alias("data_exercicio"))

        # 3. Tipagem e seleção estrita na ordem do contrato Silver
        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
