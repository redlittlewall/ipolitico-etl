import logging
from typing import Any, Dict

import polars as pl

from ipolitico.core.constants import ApiParams
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


class CamaraDespesasTransformer(BaseTransformer):
    """
    Transformer responsável pela regra de negócio das Despesas (Cota Parlamentar).

    Padroniza nomes de colunas do Bulk/API, formata datas e converte moeda
    brasileira para tipo numérico seguro (Float64).
    """

    def transform(self, df: pl.DataFrame, **kwargs: Dict[str, Any]) -> pl.DataFrame:
        """
        Limpa e normaliza o dataframe bruto de despesas.
        Aplica padronização de nomenclatura, conversão de moedas e
        blindagem de schema para evitar conflitos de tipos em execução assíncrona.

        Args:
            df (pl.DataFrame): DataFrame bruto vindo do Extractor (Camada Bronze).

        Returns:
            pl.DataFrame: DataFrame com tipagem segura e padronizada (Camada Silver).
        """
        if df.is_empty():
            return df

        # Padronização de Nomes (Resolve mismatch entre Bulk CSV e API JSON)
        mapping = {
            "nuDeputadoId": ApiParams.DEPUTADO_ID.value,
            "datEmissao": ApiParams.DATA_DOCUMENTO.value,
            "vlrDocumento": "valorDocumento",
            "vlrLiquido": "valorLiquido",
            "txtFornecedor": "nomeFornecedor",
            "txtCNPJCPF": "cnpjCpfFornecedor",
            "cnpjCpf": "cnpjCpfFornecedor",
            "ideDocumento": "codDocumento",
            "txtNumero": "numDocumento",
            "txtDescricao": "tipoDespesa",
        }
        df = df.rename({k: v for k, v in mapping.items() if k in df.columns})

        # BLINDAGEM DE SCHEMA:
        # Essas colunas podem conter apenas números em alguns lotes, induzindo o Polars ao erro.
        string_columns = [
            "cnpjCpfFornecedor",
            "numDocumento",
            "codDocumento",
            "numLote",
            "parcela",
            "idDocumento",
        ]

        existing_str_cols = [c for c in string_columns if c in df.columns]
        if existing_str_cols:
            df = df.with_columns(
                [pl.col(c).cast(pl.String, strict=False) for c in existing_str_cols]
            )

        # Transformações de Tipos (Datas, Moedas e Inteiros)
        transformations = []

        if ApiParams.DATA_DOCUMENTO.value in df.columns:
            transformations.append(
                pl.col(ApiParams.DATA_DOCUMENTO.value).str.to_datetime(strict=False)
            )

        if "valorLiquido" in df.columns:
            transformations.append(self._parse_br_currency(df, "valorLiquido"))

        if "valorDocumento" in df.columns:
            transformations.append(self._parse_br_currency(df, "valorDocumento"))

        if transformations:
            df = df.with_columns(transformations)

        # =====================================================================
        # BLINDAGEM ESTrita DE SCHEMA (Data Contract)
        # =====================================================================
        target_col = ApiParams.DEPUTADO_ID.value

        # Define as colunas exatas e seus tipos obrigatórios
        EXPECTED_SCHEMA = {
            target_col: pl.Int64,
            "ano": pl.Int64,
            "mes": pl.Int64,
            "codDocumento": pl.String,
            "numDocumento": pl.String,
            "tipoDespesa": pl.String,
            "parcela": pl.Int64,
            ApiParams.DATA_DOCUMENTO.value: pl.Datetime,
            "valorDocumento": pl.Float64,
            "valorLiquido": pl.Float64,
            "nomeFornecedor": pl.String,
            "cnpjCpfFornecedor": pl.String,
        }

        try:
            # Valida se todas as colunas existem
            missing_cols = [col for col in EXPECTED_SCHEMA.keys() if col not in df.columns]
            if missing_cols:
                raise ValueError(f"A API omitiu colunas obrigatórias: {missing_cols}")

            # Força a seleção estrita e o cast. Se a API mudou tipos, isso quebra.
            df = df.select(
                [pl.col(col).cast(dtype, strict=True) for col, dtype in EXPECTED_SCHEMA.items()]
            )

        except Exception as e:
            logger.error(f"[ALERTA CÍVICO] Quebra de Contrato da API detectada: {e}")
            # Retorna Vazio. O Consumer não salvará lixo no Data Lake.
            return pl.DataFrame()

        return df

    def _parse_br_currency(self, df: pl.DataFrame, col_name: str) -> pl.Expr:
        """
        Gera a expressão Polars para converter string de moeda BR (ex: '1.234,56') para float.
        Verifica o schema do DataFrame dinamicamente para evitar colisão de expressões.

        Args:
            df (pl.DataFrame): DataFrame contendo o schema a ser inspecionado.
            col_name (str): Nome da coluna contendo os valores financeiros.

        Returns:
            pl.Expr: Expressão do Polars pronta para o with_columns.
        """
        col_dtype = df.schema[col_name]

        # Se for String (ou Utf8 no Polars), aplicamos os replaces de pontuação
        if col_dtype in [pl.String, getattr(pl, "Utf8", pl.String)]:
            return (
                pl.col(col_name)
                .str.replace_all(r"\.", "")
                .str.replace(r",", ".")
                .cast(pl.Float64, strict=False)
                .alias(col_name)
            )

        # Se já for numérico (ou nulo), fazemos apenas o cast seguro direto
        return pl.col(col_name).cast(pl.Float64, strict=False).alias(col_name)
