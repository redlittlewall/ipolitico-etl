from typing import Any

import polars as pl
from ipolitico.transformers.base import BaseTransformer


class CamaraVotacoesTransformer(BaseTransformer):
    """
    Transformer responsável pelo domínio de Votações e Votos.

    Lida com o achatamento (flattening) de estruturas JSON aninhadas da API
    e renomeação de colunas do Bulk para um schema único e coeso.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma dados de votações ou votos, dependendo do contexto.

        Args:
            df (pl.DataFrame): DataFrame bruto.
            **kwargs (Any): Parâmetros de contexto. Use `sub_domain="votos"`
                            para aplicar a lógica de extração de votos nominais.

        Returns:
            pl.DataFrame: DataFrame padronizado.
        """
        if df.is_empty():
            return df

        sub_domain = kwargs.get("sub_domain", "votacoes")

        if sub_domain == "votacoes":
            # Lógica do cabeçalho da votação (antigo VotacoesBulkExtractor)
            date_cols = ["data", "dataHoraRegistro"]
            transformations = [
                pl.col(c).str.to_datetime(strict=False) for c in date_cols if c in df.columns
            ]
            if transformations:
                df = df.with_columns(transformations)

        elif sub_domain == "votos":
            # 1. Tratamento da API: Achatamento do Struct (antigo loop do python no extract_votos)
            # No Polars, dicionários aninhados viram o tipo Struct.
            if "deputado_" in df.columns and isinstance(df.schema["deputado_"], pl.Struct):
                df = df.with_columns(
                    [
                        pl.col("deputado_").struct.field("id").alias("deputado_id"),
                        pl.col("deputado_").struct.field("siglaPartido").alias("partido_no_voto"),
                        pl.col("deputado_").struct.field("siglaUf").alias("uf_no_voto"),
                    ]
                ).drop("deputado_")

            # 2. Tratamento do Bulk: Renomeação de schema (antigo VotosBulkExtractor)
            mapping = {"idDeputado": "deputado_id"}
            df = df.rename({k: v for k, v in mapping.items() if k in df.columns})

            # 3. Tipagem forte da Chave Estrangeira
            if "deputado_id" in df.columns:
                df = df.with_columns(pl.col("deputado_id").cast(pl.Int64, strict=False))

        return df
