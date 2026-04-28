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
        }

        df = df.rename({k: v for k, v in mapping.items() if k in df.columns})

        # Conversão de Datas e Números
        return df.with_columns(
            [
                pl.col("dataDocumento").str.to_datetime(strict=False),
                pl.col("valorLiquido").str.replace(",", ".").cast(pl.Float64, strict=False),
                pl.col("valorDocumento").str.replace(",", ".").cast(pl.Float64, strict=False),
                pl.col("id_deputado").cast(pl.Int64, strict=False),
            ]
        )
