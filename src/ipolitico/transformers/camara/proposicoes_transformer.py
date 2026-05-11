from typing import Any

import polars as pl
from ipolitico.transformers.base import BaseTransformer


class CamaraProposicoesTransformer(BaseTransformer):
    """
    Transformer responsável pelas regras de negócio de Proposições Legislativas.

    Aplica castings de datas e padronizações estritas, consolidando as lógicas
    que antes ficavam dispersas nos extratores Bulk e API.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Executa a transformação e tipagem do DataFrame de proposições.

        Args:
            df (pl.DataFrame): DataFrame bruto da camada Bronze.
            **kwargs (Any): Parâmetros de contexto adicionais.

        Returns:
            pl.DataFrame: DataFrame com tipagem corrigida (Silver).
        """
        if df.is_empty():
            return df

        date_cols = ["dataApresentacao"]
        transformations = [
            pl.col(c).str.to_datetime(strict=False) for c in date_cols if c in df.columns
        ]

        if transformations:
            df = df.with_columns(transformations)

        return df
