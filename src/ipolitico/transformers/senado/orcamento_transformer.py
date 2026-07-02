"""Transformadores para os domínios de orçamento do Senado.

Inclui:
- ``OrcamentoEmendasTransformer`` — mapeia campos do envelope ``orcamento/lista``
  para o schema Silver snake_case.
- ``OrcamentoOficiosTransformer`` — mapeia campos flat de ``orcamento/oficios``,
  serializa o array ``emendas`` como JSON string.
"""

from __future__ import annotations

import json
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

# Mapeamento dos campos da API → colunas Silver para ORCAMENTO_EMENDAS
_EMENDAS_FIELD_MAP: dict[str, tuple[str, type]] = {
    "NomeAutorOrcamento": ("nome_autor_orcamento", pl.String),
    "IndicadorAtivo": ("indicador_ativo", pl.String),
    "EmailAutorOrcamento": ("email_autor_orcamento", pl.String),
    "CodigoAutorOrcamento": ("codigo_autor_orcamento", pl.Int64),
    "DataOperacao": ("data_operacao", pl.String),
    "QuantidadeEmendas": ("quantidade_emendas", pl.Int64),
    "AnoExecucao": ("ano_execucao", pl.Int64),
    "NumeroMateria": ("numero_materia", pl.Int64),
    "AnoMateria": ("ano_materia", pl.Int64),
    "SiglaTipoPlOrcamento": ("sigla_tipo_pl_orcamento", pl.String),
    "DescricaoTipoPlOrcamento": ("descricao_tipo_pl_orcamento", pl.String),
}

# Mapeamento dos campos da API → colunas Silver para ORCAMENTO_OFICIOS
_OFICIOS_FIELD_MAP: dict[str, tuple[str, type]] = {
    "id": ("id", pl.Int64),
    "tratamento": ("tratamento", pl.String),
    "nome": ("nome", pl.String),
    "numeroProtocoloApresentacao": ("numero_protocolo_apresentacao", pl.String),
    "dataInclusao": ("data_inclusao", pl.String),
}


class OrcamentoEmendasTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de lotes de emendas.

    O DataFrame de entrada contém campos CamelCase provenientes do
    envelope XML-heritage da API. O transformer renomeia para snake_case,
    aplica tipagem estrita e descarta colunas extras.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma DataFrame bruto de emendas conforme contrato Silver.

        Args:
            df: DataFrame com campos CamelCase da API.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com schema Silver (snake_case, tipado).
            Retorna DataFrame vazio se a entrada for vazia.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.ORCAMENTO_EMENDAS.value]

        # ── Renomeia campos disponíveis ────────────────────────────────────
        for api_name, (silver_col, _dtype) in _EMENDAS_FIELD_MAP.items():
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                df = df.rename({api_name: silver_col})

        # ── Adiciona colunas faltantes como null ───────────────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])


class OrcamentoOficiosTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de ofícios orçamentários.

    O DataFrame de entrada contém campos flat + o campo ``emendas``
    (lista de dicts). O transformer renomeia para snake_case, serializa
    o array ``emendas`` como string JSON, aplica tipagem estrita e
    descarta colunas extras.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma DataFrame bruto de ofícios conforme contrato Silver.

        Args:
            df: DataFrame com campos flat da API + array ``emendas``.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com schema Silver (snake_case, tipado, ``emendas``
            como string JSON). Retorna DataFrame vazio se a entrada for
            vazia.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.ORCAMENTO_OFICIOS.value]

        # ── Serializa campo 'emendas' se presente ──────────────────────────
        if "emendas" in df.columns and df.schema["emendas"] != pl.Null:
            df = df.with_columns(
                pl.col("emendas")
                .map_elements(
                    lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else str(x),
                    return_dtype=pl.String,
                )
                .alias("emendas")
            )

        # ── Renomeia campos disponíveis ────────────────────────────────────
        for api_name, (silver_col, _dtype) in _OFICIOS_FIELD_MAP.items():
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                df = df.rename({api_name: silver_col})

        # ── Adiciona colunas faltantes como null ───────────────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
