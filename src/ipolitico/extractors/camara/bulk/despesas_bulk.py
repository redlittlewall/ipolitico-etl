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

        # Filtra para renomear apenas colunas que realmente existem no arquivo
        cols_to_rename = {k: v for k, v in mapping.items() if k in df.columns}

        return df.rename(cols_to_rename)
