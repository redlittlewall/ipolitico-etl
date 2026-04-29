import polars as pl

from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


class VotacoesBulkExtractor(BaseBulkExtractor):
    # O domínio "votacoes" fará o download do CSV de Votações (Cabeçalho)
    # Para extrair os votos, você pode passar domain="votos" no main, e a Factory
    # instanciará a mesma classe, pois o motor resolve a URL no registry.
    domain_name = "votacoes"

    def _standardize_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        date_cols = ["data", "dataHoraRegistro"]

        transformations = [
            pl.col(c).str.to_datetime(strict=False) for c in date_cols if c in df.columns
        ]

        if transformations:
            df = df.with_columns(transformations)

        return df


class VotosBulkExtractor(BaseBulkExtractor):
    domain_name = "votos"

    def _standardize_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        mapping = {"idDeputado": "deputado_id"}
        df = df.rename({k: v for k, v in mapping.items() if k in df.columns})

        if "deputado_id" in df.columns:
            df = df.with_columns(pl.col("deputado_id").cast(pl.Int64, strict=False))

        return df
