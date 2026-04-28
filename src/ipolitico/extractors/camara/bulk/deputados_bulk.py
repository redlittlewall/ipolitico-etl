import polars as pl

from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


class DeputadosBulkExtractor(BaseBulkExtractor):
    domain_name = "deputados"

    def _standardize_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        """Extrai o ID numérico da URI para igualar ao schema da API."""
        if "uri" in df.columns and "id" not in df.columns:
            df = df.with_columns(
                pl.col("uri").str.split("/").list.last().cast(pl.Int64).alias("id")
            )
        return df
