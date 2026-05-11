from typing import Any

import polars as pl
from ipolitico.transformers.base import BaseTransformer


class CamaraDeputadosTransformer(BaseTransformer):
    """
    Transformer responsável pela padronização dos dados de Deputados Federais.

    Gere a lista principal de deputados, extração de Chaves Primárias baseadas
    em URIs e serialização de estruturas complexas para salvar no banco/DataLake.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """
        Executa a transformação dos dados cadastrais e atributos dos deputados.

        Args:
            df (pl.DataFrame): DataFrame bruto.
            **kwargs (Any): Parâmetros de contexto. Use `is_child_entity=True`
                            para renomear automaticamente a PK 'id' para 'id_deputado'.

        Returns:
            pl.DataFrame: DataFrame limpo e tipado para a camada Silver.

        Raises:
            ValueError: Se o schema de ID primário quebrar o contrato da arquitetura.
        """
        if df.is_empty():
            return df

        # 1. Recuperação de ID a partir da URI (Schema Mismatch Handler)
        uri_col = next((c for c in df.columns if c.lower() == "uri"), None)
        id_col = next((c for c in df.columns if c.lower() == "id"), None)

        if uri_col and not id_col:
            df = df.with_columns(
                pl.col(uri_col).str.split("/").list.get(-1).cast(pl.Int64, strict=False).alias("id")
            )
            df = df.drop_nulls(subset=["id"])
        elif id_col and id_col != "id":
            df = df.rename({id_col: "id"})

        # 2. Tratamento de Chave Estrangeira (Injeção de Contexto via Orquestrador)
        is_child_entity = kwargs.get("is_child_entity", False)
        target_id_col = "id_deputado" if is_child_entity else "id"

        if "id" in df.columns and is_child_entity:
            df = df.rename({"id": "id_deputado"})

        if target_id_col not in df.columns:
            raise ValueError(
                f"[ERRO DE CONTRATO] Coluna identificadora '{target_id_col}' ausente. "
                f"Colunas retornadas: {df.columns}."
            )

        # 3. Tipagem Forte de IDs
        cols_to_int = [target_id_col, "idLegislatura", "idLegislaturaInicial", "idLegislaturaFinal"]
        df = df.with_columns(
            [pl.col(c).cast(pl.Int64, strict=False) for c in cols_to_int if c in df.columns]
        )

        # 4. Achatamento (Flattening) Estrito de JSONs para Persistência
        # Polars detecta dicts/lists como Struct/List. Convertê-los para String
        # previne crashes ao salvar no SQLite ou Parquet não-aninhado.
        struct_or_list_cols = [
            col for col in df.columns if isinstance(df.schema[col], (pl.Struct, pl.List))
        ]
        if struct_or_list_cols:
            df = df.with_columns([pl.col(c).to_json().alias(c) for c in struct_or_list_cols])

        return df
