import polars as pl

from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


class ProposicoesBulkExtractor(BaseBulkExtractor):
    domain_name = "proposicoes"

    def _standardize_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        date_cols = ["dataApresentacao"]

        transformations = [
            pl.col(c).str.to_datetime(strict=False) for c in date_cols if c in df.columns
        ]

        if transformations:
            df = df.with_columns(transformations)

        return df
