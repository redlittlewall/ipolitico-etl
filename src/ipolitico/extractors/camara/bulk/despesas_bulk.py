import polars as pl

from ipolitico.extractors.camara.bulk.base_bulk import BaseBulkExtractor


class DespesasBulkExtractor(BaseBulkExtractor):
    """Extrator focado nos Dumps ZIP anuais de Cotas Parlamentares (CEAP)."""

    domain_name = "despesas"

    def _standardize_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Padroniza os nomes das colunas do CSV para ficarem idênticos
        aos nomes devolvidos pela API JSON.
        """
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

        transformations = []

        if "dataDocumento" in df.columns:
            transformations.append(pl.col("dataDocumento").str.to_datetime(strict=False))

        def parse_br_currency(col_name):
            return (
                pl.col(col_name)
                .str.replace_all(r"\.", "")
                .str.replace(",", ".")
                .cast(pl.Float64, strict=False)
            )

        if "valorLiquido" in df.columns:
            transformations.append(parse_br_currency("valorLiquido"))

        if "valorDocumento" in df.columns:
            transformations.append(parse_br_currency("valorDocumento"))

        if "id_deputado" in df.columns:
            transformations.append(pl.col("id_deputado").cast(pl.Int64, strict=False))

        if transformations:
            df = df.with_columns(transformations)
        return df
