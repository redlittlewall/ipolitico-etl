from typing import Any

import polars as pl
from ipolitico.transformers.base import BaseTransformer


class CamaraDespesasTransformer(BaseTransformer):
    """
    Transformer responsável pela regra de negócio das Despesas (Cota Parlamentar).

    Padroniza nomes de colunas do Bulk/API, formata datas e converte moeda
    brasileira para tipo numérico seguro (Float64).
    """

    def _parse_br_currency(self, col_name: str) -> pl.Expr:
        """
        Converte uma string de moeda no formato brasileiro para float.

        Args:
            col_name (str): Nome da coluna contendo os valores (ex: "1.250,50").

        Returns:
            pl.Expr: Expressão do Polars para limpar e converter a coluna para Float64.
        """
        return (
            pl.col(col_name)
            .str.replace_all(r"\.", "")
            .str.replace(",", ".")
            .cast(pl.Float64, strict=False)
        )

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Executa a limpeza e padronização do DataFrame de despesas.

        Args:
            df (pl.DataFrame): DataFrame bruto oriundo da camada Bronze.
            **kwargs (Any): Parâmetros de contexto adicionais.

        Returns:
            pl.DataFrame: DataFrame transformado, pronto para a camada Silver.
        """
        if df.is_empty():
            return df

        # 1. Padronização de Nomes (Resolve mismatch entre Bulk CSV e API JSON)
        mapping = {
            "nuDeputadoId": "id_deputado",
            "datEmissao": "dataDocumento",
            "vlrDocumento": "valorDocumento",
            "vlrLiquido": "valorLiquido",
            "txtFornecedor": "nomeFornecedor",
            "txtCNPJCPF": "cnpjCpfFornecedor",
            "ideDocumento": "codDocumento",
            "txtNumero": "numDocumento",
            "txtDescricao": "tipoDespesa",
        }
        df = df.rename({k: v for k, v in mapping.items() if k in df.columns})

        # 2. Transformações de Tipos e Limpeza
        transformations = []

        if "dataDocumento" in df.columns:
            transformations.append(pl.col("dataDocumento").str.to_datetime(strict=False))

        if "valorLiquido" in df.columns:
            transformations.append(self._parse_br_currency("valorLiquido"))

        if "valorDocumento" in df.columns:
            transformations.append(self._parse_br_currency("valorDocumento"))

        if "id_deputado" in df.columns:
            transformations.append(pl.col("id_deputado").cast(pl.Int64, strict=False))

        if transformations:
            df = df.with_columns(transformations)

        return df
