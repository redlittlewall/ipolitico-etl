"""Transformador para o domínio PROCESSOS — mapeia campos flat da API."""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

# Mapeamento dos campos flat da API → colunas Silver
_FIELD_MAP: dict[str, tuple[str, type]] = {
    "id": ("id", pl.Int64),
    "codigoMateria": ("codigo_materia", pl.Int64),
    "identificacao": ("identificacao", pl.String),
    "ementa": ("ementa", pl.String),
    "autoria": ("autoria", pl.String),
    "tipoDocumento": ("tipo_documento", pl.String),
    "dataApresentacao": ("data_apresentacao", pl.String),
    "situacaoAtual": ("situacao_atual", pl.String),
    "dataSituacaoAtual": ("data_situacao", pl.String),
    "casaIdentificadora": ("casa_identificadora", pl.String),
    "tramitando": ("tramitando", pl.String),
}


class SenadoProcessosTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de processos.

    O DataFrame de entrada contém campos flat (sem envelopes XML).
    O transformer renomeia para snake_case e aplica tipagem estrita.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.PROCESSOS.value]

        # ── Renomeia e tipa campos disponíveis ──────────────────────────────
        for api_name, (silver_col, _dtype) in _FIELD_MAP.items():
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                df = df.rename({api_name: silver_col})

        # ── Cast dos campos do contrato ─────────────────────────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])


class SenadoProcessosDetalheTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de detalhes de processo.

    O DataFrame de entrada contém campos flat + um struct ``conteudo``
    que carrega a ementa. O transformer extrai campos-chave, renomeia
    para snake_case e descarta colunas aninhadas (documento, autoria, etc.).
    """

    _FIELD_MAP: dict[str, tuple[str, type]] = {
        "id": ("id", pl.Int64),
        "codigoMateria": ("codigo_materia", pl.Int64),
        "identificacao": ("identificacao", pl.String),
        "sigla": ("sigla", pl.String),
        "numero": ("numero", pl.String),
        "ano": ("ano", pl.Int64),
        "casaIdentificadora": ("casa_identificadora", pl.String),
        "tramitando": ("tramitando", pl.String),
        "dataInicioEfetivo": ("data_inicio_efetivo", pl.String),
        "situacaoAtual": ("situacao_atual", pl.String),
        "dataSituacaoAtual": ("data_situacao", pl.String),
    }

    _STRUCT_EXTRACT: dict[str, tuple[str, str, type]] = {
        "ementa": ("conteudo", "ementa", pl.String),
    }

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.PROCESSOS_DETALHE.value]

        # ── Renomeia campos flat disponíveis ──────────────────────────────────
        for api_name, (silver_col, _dtype) in self._FIELD_MAP.items():
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                df = df.rename({api_name: silver_col})

        # ── Extrai campos de structs aninhados ────────────────────────────────
        for silver_col, (struct_col, field_name, _dtype) in self._STRUCT_EXTRACT.items():
            if silver_col not in contract:
                continue
            if struct_col in df.columns:
                df = df.with_columns(pl.col(struct_col).struct.field(field_name).alias(silver_col))

        # ── Adiciona colunas faltantes como null ──────────────────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])


class SenadoProcessosEmendasTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de emendas.

    O DataFrame de entrada contém campos flat. O transformer renomeia
    para snake_case, serializa a lista ``decisoes`` como string e
    descarta colunas complexas (``subemendas``).
    """

    _FIELD_MAP: dict[str, tuple[str, type]] = {
        "id": ("id", pl.Int64),
        "idProcesso": ("id_processo", pl.Int64),
        "identificacao": ("identificacao", pl.String),
        "autoria": ("autoria", pl.String),
        "casa": ("casa", pl.String),
        "dataApresentacao": ("data_apresentacao", pl.String),
        "descricaoDocumentoEmenda": ("descricao", pl.String),
        "tipo": ("tipo", pl.String),
        "numero": ("numero", pl.String),
        "nomeColegiado": ("nome_colegiado", pl.String),
        "siglaColegiado": ("sigla_colegiado", pl.String),
        "urlDocumentoEmenda": ("url_documento", pl.String),
    }

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.PROCESSOS_EMENDAS.value]

        # ── Serializa lista 'decisoes' como string JSON ───────────────────────
        if "decisoes" in df.columns and df.schema["decisoes"] != pl.Null:
            df = df.with_columns(
                pl.col("decisoes")
                .list.eval(pl.element().struct.json_encode())
                .list.join(",")
                .alias("decisoes")
            )

        # ── Renomeia campos disponíveis ───────────────────────────────────────
        for api_name, (silver_col, _dtype) in self._FIELD_MAP.items():
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                df = df.rename({api_name: silver_col})

        # ── Adiciona colunas faltantes como null ──────────────────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])


class SenadoProcessosDocumentosTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de documentos.

    O DataFrame de entrada contém campos flat + um array
    ``apresentadoNosProcessos`` opcional. O transformer renomeia para
    snake_case, extrai o primeiro processo associado (se houver) e
    descarta colunas aninhadas (``autores``).
    """

    _FIELD_MAP: dict[str, tuple[str, type]] = {
        "id": ("id", pl.Int64),
        "identificacao": ("identificacao", pl.String),
        "autoria": ("autoria", pl.String),
        "casaEnteRecebedor": ("casa_ente_recebedor", pl.String),
        "casaRecebedora": ("casa_recebedora", pl.String),
        "dataDocumento": ("data_documento", pl.String),
        "dataRecebimento": ("data_recebimento", pl.String),
        "descricao": ("descricao", pl.String),
        "descricaoTipo": ("descricao_tipo", pl.String),
        "siglaTipo": ("sigla_tipo", pl.String),
        "siglaEnteRecebedor": ("sigla_entidade_recebedora", pl.String),
        "nomeEnteRecebedor": ("nome_entidade_recebedora", pl.String),
        "urlDocumento": ("url_documento", pl.String),
    }

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.PROCESSOS_DOCUMENTOS.value]

        # ── Extrai primeiro processo associado (se houver) ────────────────────
        if (
            "apresentadoNosProcessos" in df.columns
            and df.schema["apresentadoNosProcessos"] != pl.Null
        ):
            df = df.with_columns(
                pl.col("apresentadoNosProcessos").list.first().alias("_primeiro_processo")
            )
            df = df.with_columns(
                pl.col("_primeiro_processo")
                .struct.field("id")
                .cast(pl.Int64)
                .alias("apresentado_processo_id")
            )
            df = df.with_columns(
                pl.col("_primeiro_processo")
                .struct.field("identificacao")
                .alias("apresentado_processo_identificacao")
            )

        # ── Renomeia campos disponíveis ───────────────────────────────────────
        for api_name, (silver_col, _dtype) in self._FIELD_MAP.items():
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                df = df.rename({api_name: silver_col})

        # ── Adiciona colunas faltantes como null ──────────────────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
