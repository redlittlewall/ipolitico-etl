"""Mapeamento do dump CEAP (Ano-{ano}.csv) para o contrato Silver de despesas."""

from __future__ import annotations

import polars as pl

from ipolitico.core.constants import ApiParams

# Identificadores de deputado no CEAP (o dump traz os dois; não renomear em lote).
CEAP_DEPUTADO_SOURCE_COLUMNS = ("nuDeputadoId", "ideCadastro")

# Campos do arquivo CEAP documentados em dadosabertos.camara.leg.br (Cota Parlamentar)
CEAP_BULK_ALIASES: dict[str, str] = {
    "datEmissao": ApiParams.DATA_DOCUMENTO.value,
    "vlrLiquido": "valorLiquido",
    "vlrDocumento": "valorDocumento",
    "vlrGlosa": "valorGlosa",
    "txtFornecedor": "nomeFornecedor",
    "txtCNPJCPF": "cnpjCpfFornecedor",
    "ideDocumento": "codDocumento",
    "txtNumero": "numDocumento",
    "numParcela": "parcela",
    "numAno": "ano",
    "numMes": "mes",
    "txtDescricao": "tipoDespesa",
    "indTipoDocumento": "tipoDocumento",
    "urlDocumento": "urlDocumento",
}


def normalize_document_date_iso(
    df: pl.DataFrame, column: str = ApiParams.DATA_DOCUMENTO.value
) -> pl.DataFrame:
    """Converte dataDocumento para YYYY-MM-DD (API ISO ou CEAP DD/MM/YYYY)."""
    if df.is_empty() or column not in df.columns:
        return df

    raw = pl.col(column).cast(pl.Utf8, strict=False).str.strip_chars()
    iso = raw.str.slice(0, 10)
    br = raw.str.strptime(pl.Date, format="%d/%m/%Y", strict=False).dt.strftime("%Y-%m-%d")
    return df.with_columns(pl.coalesce(br, iso).alias(column))


def apply_ceap_column_aliases(df: pl.DataFrame) -> pl.DataFrame:
    """
    Renomeia colunas CEAP sem duplicar id_deputado quando nuDeputadoId e ideCadastro coexistem.
    """
    dep_col = ApiParams.DEPUTADO_ID.value
    rename_map = {
        k: v
        for k, v in CEAP_BULK_ALIASES.items()
        if k in df.columns and k not in CEAP_DEPUTADO_SOURCE_COLUMNS
    }
    if rename_map:
        df = df.rename(rename_map)

    has_nu = "nuDeputadoId" in df.columns
    has_ide = "ideCadastro" in df.columns
    if has_nu and has_ide:
        df = df.with_columns(
            pl.coalesce(
                pl.col("nuDeputadoId").cast(pl.Utf8, strict=False),
                pl.col("ideCadastro").cast(pl.Utf8, strict=False),
            ).alias(dep_col)
        ).drop("nuDeputadoId", "ideCadastro")
    elif has_nu:
        df = df.rename({"nuDeputadoId": dep_col})
    elif has_ide:
        df = df.rename({"ideCadastro": dep_col})

    return df
