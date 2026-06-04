"""Helper de locale BR para conversão de moeda no formato brasileiro."""

from typing import List

import polars as pl


def convert_br_currency_columns(df: pl.DataFrame, columns: List[str]) -> pl.DataFrame:
    """
    Converte colunas de moeda no formato brasileiro (ex: ``'1.234,56'``) para ``Float64``.

    A função elimina os separadores de milhar (``.``) e substitui a vírgula decimal
    (``,``) por ponto (``.``) antes de realizar o cast. Colunas ausentes no DataFrame
    são ignoradas silenciosamente.

    Args:
        df: DataFrame de entrada.
        columns: Lista de nomes de colunas a converter. Colunas inexistentes são
            ignoradas sem erro.

    Returns:
        pl.DataFrame: DataFrame com as colunas convertidas para ``Float64``.
            Se o DataFrame de entrada for vazio, retorna vazio com os mesmos nomes
            de coluna mas com dtype ``Float64`` para as colunas convertidas.
    """
    existing = [c for c in columns if c in df.columns]
    if not existing:
        return df

    expressions = []
    for c in existing:
        col = pl.col(c)
        if df.schema[c] == pl.String:
            col = col.str.replace_all(r"\.", "").str.replace(",", ".")
        expressions.append(col.cast(pl.Float64, strict=False).alias(c))

    return df.with_columns(expressions)
