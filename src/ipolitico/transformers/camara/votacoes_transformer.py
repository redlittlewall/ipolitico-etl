from typing import Any

import polars as pl
from ipolitico.core.constants import ApiParams, DomainType
from ipolitico.transformers.base import BaseTransformer


class CamaraVotacoesTransformer(BaseTransformer):
    """
    Transformer responsável pelo domínio de Votações e Votos.

    Lida com o achatamento (flattening) de estruturas JSON aninhadas da API
    e renomeação de colunas do Bulk para um schema único e coeso na camada Silver.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Transforma dados de votações ou votos, dependendo do contexto.

        Args:
            df (pl.DataFrame): DataFrame bruto oriundo da camada Bronze.
            **kwargs (Any): Parâmetros de contexto. Use `sub_domain=DomainType.VOTOS`
                            para aplicar a lógica de extração de votos individuais.

        Returns:
            pl.DataFrame: DataFrame padronizado e tipado para a camada Silver.
        """
        if df.is_empty():
            return df

        # Uso de Enum para evitar Magic Strings
        sub_domain = kwargs.get("sub_domain", DomainType.VOTACOES)

        if sub_domain == DomainType.VOTACOES:
            # Lógica do cabeçalho da votação
            date_cols = ["data", "dataHoraRegistro"]
            transformations = [
                pl.col(c).str.to_datetime(strict=False) for c in date_cols if c in df.columns
            ]
            if transformations:
                df = df.with_columns(transformations)

        elif sub_domain == DomainType.VOTOS:
            # 1. Tratamento da API: Achatamento do Struct (Substitui loops Python lentos)
            dep_col = "deputado_"
            if dep_col in df.columns and isinstance(df.schema[dep_col], pl.Struct):
                df = df.with_columns(
                    [
                        pl.col(dep_col).struct.field("id").alias(ApiParams.DEPUTADO_ID.value),
                        pl.col(dep_col)
                        .struct.field(ApiParams.SIGLA_PARTIDO.value)
                        .alias(ApiParams.PARTIDO_NO_VOTO.value),
                        pl.col(dep_col)
                        .struct.field(ApiParams.SIGLA_UF.value)
                        .alias(ApiParams.UF_NO_VOTO.value),
                    ]
                ).drop(dep_col)

            # 2. Tratamento do Bulk: Tradução de Schema para padrão Silver
            mapping = {"idDeputado": ApiParams.DEPUTADO_ID.value}
            df = df.rename({k: v for k, v in mapping.items() if k in df.columns})

            # 3. Tipagem forte da Chave Estrangeira
            if ApiParams.DEPUTADO_ID.value in df.columns:
                df = df.with_columns(
                    pl.col(ApiParams.DEPUTADO_ID.value).cast(pl.Int64, strict=False)
                )

        return df
