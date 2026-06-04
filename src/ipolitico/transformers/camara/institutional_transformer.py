"""Transformers para entidades institucionais (blocos, frentes, grupos, legislaturas)."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)


def _apply_contract(df: pl.DataFrame, domain_key: str) -> pl.DataFrame:
    contract = SILVER_SCHEMAS[domain_key]
    for col in contract:
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).alias(col))
    return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])


class CamaraBlocosTransformer(BaseTransformer):
    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        if "id" in df.columns:
            df = df.with_columns(pl.col("id").cast(pl.Int64, strict=False))
        return _apply_contract(df, DomainType.BLOCOS.value)


class CamaraFrentesTransformer(BaseTransformer):
    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.FRENTES.value)


class CamaraGruposTransformer(BaseTransformer):
    """Transformer para o domínio Grupos (bancadas, minoria, etc.).

    Serializa ultimoStatus (Struct da API) para string usando expressão nativa
    Polars, em vez de map_elements, para preservar paralelismo vetorizado.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        if "ultimoStatus" in df.columns:
            dtype = df.schema["ultimoStatus"]
            if isinstance(dtype, pl.Struct):
                df = df.with_columns(pl.col("ultimoStatus").struct.json_encode())
        return _apply_contract(df, DomainType.GRUPOS.value)


class CamaraLegislaturasTransformer(BaseTransformer):
    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        for col in ("dataInicio", "dataFim"):
            if col in df.columns:
                df = df.with_columns(pl.col(col).str.slice(0, 10))
        return _apply_contract(df, DomainType.LEGISLATURAS.value)


class CamaraFuncionariosTransformer(BaseTransformer):
    """Transformer para o domínio funcionarios (servidores da Câmara, bulk-only snapshot).

    O CSV bruto tem colunas como ponto (String com prefixo P_),
    codGrupo (numérico), nome, cargo, lotação etc. O transformer apenas
    aplica o contrato SILVER_SCHEMAS — a conversão de tipos numéricos é
    feita via schema_overrides no BULK_REGISTRY + _apply_contract.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.FUNCIONARIOS.value)


class CamaraTecadCategoriasTransformer(BaseTransformer):
    """Transformer para o domínio tecadCategorias (categorias do tesauro, bulk-only snapshot).

    O CSV bruto tem colunas: codCategoria, categoria, codSubCategoria, subCategoria.
    A conversão de códigos numéricos para Int64 é feita via schema_overrides
    no BULK_REGISTRY + _apply_contract.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.TECAD_CATEGORIAS.value)


class CamaraTecadTermosTransformer(BaseTransformer):
    """Transformer para o domínio tecadTermos (termos do tesauro, bulk-only snapshot).

    O CSV bruto tem colunas: codTermo, termo, categorias, subcategorias,
    notas*, use, usadoPara, termosEspecificos, termosGenericos, termosRelacionados.
    A conversão de codTermo para Int64 é feita via schema_overrides
    no BULK_REGISTRY + _apply_contract.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df
        return _apply_contract(df, DomainType.TECAD_TERMOS.value)
