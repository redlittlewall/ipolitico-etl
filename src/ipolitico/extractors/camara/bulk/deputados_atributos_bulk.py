import polars as pl

from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


class DeputadosAtributosBulkExtractor(BaseBulkExtractor):
    """
    Extrator Bulk customizado para atributos biográficos massivos dos deputados
    (ex: Profissões e Ocupações).

    Intercepta o DataFrame do CSV do Governo e padroniza a Chave Estrangeira
    para bater exatamente com a nomenclatura usada pela nossa API,
    prevenindo o erro de 'Schema Mismatch' no Data Lake.
    """

    def _standardize_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        # Primeiro, roda a Limpeza Nuclear padrão do BaseBulkExtractor
        df = super()._standardize_schema(df)

        # Em seguida, aplica a mutação de chave estrangeira
        if "id" in df.columns:
            df = df.rename({"id": "id_deputado"})

        return df
