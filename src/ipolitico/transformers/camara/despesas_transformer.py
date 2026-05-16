import logging
from typing import Any, Dict

import polars as pl

from ipolitico.core.constants import ApiParams, DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
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

        bulk_aliases = {
            "nuDeputadoId": "id_deputado",
            "datEmissao": ApiParams.DATA_DOCUMENTO.value,
            "vlrLiquido": "valorLiquido",
            "vlrDocumento": "valorDocumento",
            "vlrGlosa": "valorGlosa",
            "txtFornecedor": "nomeFornecedor",
        }
        df = df.rename({k: v for k, v in bulk_aliases.items() if k in df.columns})

        if ApiParams.DATA_DOCUMENTO.value in df.columns:
            df = df.with_columns(
                pl.col(ApiParams.DATA_DOCUMENTO.value)
                .str.slice(0, 10)
                .alias(ApiParams.DATA_DOCUMENTO.value)
            )

        flt = kwargs.get("bulk_temporal_filter")
        if flt:
            from ipolitico.transformers.bulk_window import apply_bulk_temporal_filter

            fc, lo, hi = flt
            df = apply_bulk_temporal_filter(df, fc, lo, hi)
            if df.is_empty():
                return df

        for col_moeda in ["valorLiquido", "valorDocumento", "valorGlosa"]:
            if col_moeda in df.columns and df.schema[col_moeda] == pl.String:
                df = df.with_columns(
                    pl.col(col_moeda)
                    .str.replace_all(r"\.", "")
                    .str.replace(r",", ".")
                    .alias(col_moeda)
                )

        contract = SILVER_SCHEMAS[DomainType.DESPESAS.value]

        try:
            # Filtra colunas indesejadas (lixo da API)
            cols_to_keep = [c for c in contract.keys() if c in df.columns]
            df = df.select(cols_to_keep)

            # Injeta Nulos para colunas do contrato que a API omitiu (ex: valorGlosa)
            for expected_col, dtype in contract.items():
                if expected_col not in df.columns:
                    df = df.with_columns(pl.lit(None).alias(expected_col))

            # Cast em massa otimizado (strict=False para converter strings numéricas limpadas)
            df = df.select(
                [pl.col(col).cast(dtype, strict=False) for col, dtype in contract.items()]
            )

            # Filtro Cívico: Remove notas sem código (corrompidas) e com valor zero
            df = df.filter((pl.col("codDocumento").is_not_null()) & (pl.col("valorLiquido") != 0.0))

        except Exception as e:
            logger.error(f"[ALERTA CÍVICO] Quebra de Contrato da API detectada: {e}")
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
