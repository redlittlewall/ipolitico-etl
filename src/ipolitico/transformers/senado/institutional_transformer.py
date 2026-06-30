"""Transformers para dados rasos de comissões do Senado.

Compartilha a função ``_apply_senado_contract`` entre os 4 domínios,
similar ao ``InstitutionalTransformer`` da Câmara.
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

logger = logging.getLogger(__name__)

# ── Mapeamentos de campo: API → Silver ──────────────────────────────────────

_COMISSOES_LISTA_FIELD_MAP: dict[str, tuple[str, type]] = {
    "Codigo": ("codigo", pl.Int64),
    "Sigla": ("sigla", pl.String),
    "Nome": ("nome", pl.String),
    "DataInicio": ("data_inicio", pl.String),
    "Publica": ("publica", pl.String),
    "CodigoTipoColegiado": ("codigo_tipo_colegiado", pl.Int64),
    "SiglaTipoColegiado": ("sigla_tipo_colegiado", pl.String),
    "DescricaoTipoColegiado": ("descricao_tipo_colegiado", pl.String),
    "SiglaCasa": ("sigla_casa", pl.String),
    "Finalidade": ("finalidade", pl.String),
}

_COMISSOES_DETALHE_FIELD_MAP: dict[str, tuple[str, type]] = {
    "CodigoColegiado": ("codigo", pl.Int64),
    "NomeColegiado": ("nome", pl.String),
    "SiglaColegiado": ("sigla", pl.String),
    "DataInicio": ("data_inicio", pl.String),
    "Cargos": ("cargos", pl.String),
    "Requerimentos": ("requerimentos", pl.String),
    "QuantidadesMembros": ("quantidades_membros", pl.String),
}

_COMISSOES_REUNIOES_FIELD_MAP: dict[str, tuple[str, type]] = {
    "codigo": ("codigo", pl.Int64),
    "versao": ("versao", pl.String),
    "descricao": ("descricao", pl.String),
    "titulo": ("titulo", pl.String),
    "CodigoColegiado": ("codigo_colegiado", pl.Int64),
    "SiglaColegiado": ("sigla_colegiado", pl.String),
    "NomeColegiado": ("nome_colegiado", pl.String),
    "dataInicio": ("data_inicio", pl.String),
    "local": ("local", pl.String),
    "situacao": ("situacao", pl.String),
    "status": ("status", pl.String),
    "secreta": ("secreta", pl.String),
    "tipoPresenca": ("tipo_presenca", pl.String),
    "realizada": ("realizada", pl.String),
    "confirmada": ("confirmada", pl.String),
    "codigoSituacao": ("codigo_situacao", pl.Int64),
    "linkECidadania": ("link_ecidadania", pl.String),
    "urlUltimaPautaSimplesPublicada": ("url_ultima_pauta_simples", pl.String),
    "urlUltimaPautaCheiaPublicada": ("url_ultima_pauta_cheia", pl.String),
    "urlUltimoResultadoPublicado": ("url_ultimo_resultado", pl.String),
}

_COMISSOES_MEMBROS_FIELD_MAP: dict[str, tuple[str, type]] = {
    "CodigoComissao": ("codigo_comissao", pl.Int64),
    "SiglaComissao": ("sigla_comissao", pl.String),
    "NomeComissao": ("nome_comissao", pl.String),
    "NomeMembro": ("nome_membro", pl.String),
    "CodigoMembro": ("codigo_membro", pl.Int64),
    "TipoVaga": ("tipo_vaga", pl.String),
    "IndicadorVagaAtiva": ("indicador_vaga_ativa", pl.String),
    "DataInicioMembroVaga": ("data_inicio_membro_vaga", pl.String),
}


def _apply_senado_contract(
    df: pl.DataFrame,
    field_map: dict[str, tuple[str, type]],
    domain_key: str,
) -> pl.DataFrame:
    """Aplica o contrato Silver a um DataFrame usando FIELD_MAP + schema.

    Renomeia colunas do nome da API para snake_case via ``field_map``,
    adiciona colunas faltantes como NULL, serializa structs remanescentes
    como JSON string, e aplica cast estrito conforme o contrato Silver.

    Args:
        df: DataFrame bruto (colunas no formato da API).
        field_map: Dict ``{api_name: (silver_name, dtype)}``.
        domain_key: Chave no ``SILVER_SCHEMAS`` (ex: ``DomainType.COMISSOES_SENADO.value``).

    Returns:
        DataFrame com colunas e tipos do contrato Silver.
    """
    if df.is_empty():
        return df

    contract = SILVER_SCHEMAS[domain_key]

    # ── Renomeia colunas disponíveis ────────────────────────────────────────
    for api_name, (silver_col, _dtype) in field_map.items():
        if silver_col not in contract:
            continue
        if api_name in df.columns:
            df = df.rename({api_name: silver_col})

    # ── Serializa structs remanescentes como JSON ─────────────────────────────
    for col in df.columns:
        dtype = df.schema.get(col)
        if dtype is not None and isinstance(dtype, pl.Struct):
            df = df.with_columns(pl.col(col).struct.json_encode())

    # ── Adiciona colunas faltantes como null ────────────────────────────────
    for col in contract:
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).alias(col))

    return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])


class SenadoComissoesListaTransformer(BaseTransformer):
    """Aplica contrato Silver à lista de comissões do Senado."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma DataFrame bruto da lista de comissões.

        Args:
            df: DataFrame com colunas da API (Codigo, Sigla, Nome, ...).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame no schema Silver de ``comissoes_senado``.
        """
        return _apply_senado_contract(
            df, _COMISSOES_LISTA_FIELD_MAP, DomainType.COMISSOES_SENADO.value
        )


class SenadoComissoesDetalheTransformer(BaseTransformer):
    """Aplica contrato Silver aos detalhes de comissão.

    Serializa colunas struct (Cargos, Requerimentos, QuantidadesMembros)
    como JSON string.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma DataFrame bruto dos detalhes da comissão.

        Args:
            df: DataFrame com colunas da API (CodigoColegiado, Cargos, ...).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame no schema Silver de ``comissoes_detalhe``.
        """
        return _apply_senado_contract(
            df, _COMISSOES_DETALHE_FIELD_MAP, DomainType.COMISSOES_DETALHE.value
        )


class SenadoComissoesReunioesTransformer(BaseTransformer):
    """Aplica contrato Silver à agenda de reuniões de comissão."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma DataFrame bruto da agenda de reuniões.

        Args:
            df: DataFrame com colunas da API (codigo, titulo, CodigoColegiado, ...).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame no schema Silver de ``comissoes_reunioes``.
        """
        return _apply_senado_contract(
            df, _COMISSOES_REUNIOES_FIELD_MAP, DomainType.COMISSOES_REUNIOES.value
        )


class SenadoComissoesMembrosTransformer(BaseTransformer):
    """Aplica contrato Silver à composição de membros de comissão."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma DataFrame bruto dos membros da comissão.

        Args:
            df: DataFrame com colunas da API (CodigoMembro, NomeMembro, ...).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame no schema Silver de ``comissoes_membros``.
        """
        return _apply_senado_contract(
            df, _COMISSOES_MEMBROS_FIELD_MAP, DomainType.COMISSOES_MEMBROS.value
        )
