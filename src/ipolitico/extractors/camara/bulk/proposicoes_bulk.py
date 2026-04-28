import polars as pl

from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


class ProposicoesBulkExtractor(BaseBulkExtractor):
    domain_name = "proposicoes"

    def _standardize_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        # O CSV de proposições tem um schema muito próximo ao da API.
        # Adicione mapeamentos aqui futuramente caso encontre anomalias nos relatórios do DuckDB.
        return df
