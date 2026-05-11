from typing import Any

import polars as pl
from ipolitico.core.constants import ApiParams
from ipolitico.transformers.base import BaseTransformer


class CamaraDeputadosTransformer(BaseTransformer):
    """
    Transformer responsável pela padronização dos dados de Deputados Federais.

    Gere a lista principal de deputados, extração de Chaves Primárias baseadas
    em URIs e serialização de estruturas complexas para salvar no banco/DataLake.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        # 1. Recuperação de ID a partir da URI
        uri_col = next((c for c in df.columns if c.lower() == "uri"), None)
        id_col = next((c for c in df.columns if c.lower() == ApiParams.ID.value), None)

        if uri_col and not id_col:
            df = df.with_columns(
                pl.col(uri_col)
                .str.split("/")
                .list.get(-1)
                .cast(pl.Int64, strict=False)
                .alias(ApiParams.ID.value)
            )
            df = df.drop_nulls(subset=[ApiParams.ID.value])
        elif id_col and id_col != ApiParams.ID.value:
            df = df.rename({id_col: ApiParams.ID.value})

        # 2. Tratamento de Chave Estrangeira (Injeção de Contexto via Orquestrador)
        is_child_entity = kwargs.get("is_child_entity", False)
        target_id_col = ApiParams.DEPUTADO_ID.value if is_child_entity else ApiParams.ID.value

        if ApiParams.ID.value in df.columns and is_child_entity:
            df = df.rename({ApiParams.ID.value: ApiParams.DEPUTADO_ID.value})

        if target_id_col not in df.columns:
            raise ValueError(
                f"[ERRO DE CONTRATO] Coluna identificadora '{target_id_col}' ausente. "
                f"Colunas retornadas: {df.columns}."
            )

        # 3. Tipagem Forte de IDs
        cols_to_int = [
            target_id_col,
            ApiParams.ID_LEGISLATURA.value,
            "idLegislaturaInicial",
            "idLegislaturaFinal",
        ]
        df = df.with_columns(
            [pl.col(c).cast(pl.Int64, strict=False) for c in cols_to_int if c in df.columns]
        )

        # 4. Achatamento (Flattening) Estrito de JSONs para Persistência
        struct_or_list_cols = [
            col for col in df.columns if isinstance(df.schema[col], (pl.Struct, pl.List))
        ]
        if struct_or_list_cols:
            df = df.with_columns([pl.col(c).to_json().alias(c) for c in struct_or_list_cols])

        return df
