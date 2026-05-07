import polars as pl

from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


class DeputadosBulkExtractor(BaseBulkExtractor):
    domain_name = "deputados"

    def _standardize_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        """Extrai o ID numérico da URI para igualar ao schema da API."""
        uri_col = next((c for c in df.columns if c.lower() == "uri"), None)
        id_col = next((c for c in df.columns if c.lower() == "id"), None)

        if uri_col and not id_col:
            df = df.with_columns(
                pl.col(uri_col).str.split("/").list.get(-1).cast(pl.Int64, strict=False).alias("id")
            )
            df = df.drop_nulls(subset=["id"])
        elif id_col and id_col != "id":
            df = df.rename({id_col: "id"})

        if "id" not in df.columns:
            raise ValueError(
                f"[ERRO DE CONTRATO] Schema da Câmara alterado! Colunas retornadas: {df.columns}."
                f"Impossível mapear a PK 'id'."
            )

        cols_to_int = ["id", "idLegislatura"]
        return df.with_columns(
            [pl.col(c).cast(pl.Int64, strict=False) for c in cols_to_int if c in df.columns]
        )
