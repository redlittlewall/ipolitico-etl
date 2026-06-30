"""Transformadores para os domínios de discursos e notas taquigráficas.

Mapeia campos flat da API do Senado (PascalCase) para snake_case conforme
os contratos SILVER_SCHEMAS.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

# ── Field maps ────────────────────────────────────────────────────────────────

_FIELD_MAP_PLENARIO: dict[str, tuple[str, type]] = {
    "Codigo": ("codigo", pl.Int64),
    "Data": ("data", pl.String),
    "TipoDiscurso": ("tipo_discurso", pl.String),
    "Fase": ("fase", pl.String),
    "Resumo": ("resumo", pl.String),
    "NomeParlamentar": ("nome_parlamentar", pl.String),
    "SiglaPartido": ("sigla_partido", pl.String),
    "UF": ("uf", pl.String),
}

_FIELD_MAP_SENADOR: dict[str, tuple[str, type]] = {
    "Codigo": ("codigo", pl.Int64),
    "CodigoParlamentar": ("codigo_parlamentar", pl.Int64),
    "NomeParlamentar": ("nome_parlamentar", pl.String),
    "SiglaPartido": ("sigla_partido", pl.String),
    "UF": ("uf", pl.String),
    "Data": ("data", pl.String),
    "Hora": ("hora", pl.String),
    "TipoDiscurso": ("tipo_discurso", pl.String),
    "Resumo": ("resumo", pl.String),
    "Texto": ("texto", pl.String),
}

_FIELD_MAP_TEXTO: dict[str, tuple[str, type]] = {
    "Codigo": ("codigo", pl.Int64),
    "Texto": ("texto", pl.String),
}

_FIELD_MAP_SESSAO: dict[str, tuple[str, type]] = {
    "IdSessao": ("id_sessao", pl.Int64),
    "CodigoSessao": ("id_sessao", pl.Int64),
    "Texto": ("texto", pl.String),
}

_FIELD_MAP_REUNIAO: dict[str, tuple[str, type]] = {
    "IdReuniao": ("id_reuniao", pl.Int64),
    "CodigoReuniao": ("id_reuniao", pl.Int64),
    "Texto": ("texto", pl.String),
}


# ── Helper ────────────────────────────────────────────────────────────────────


def _apply_contract(
    df: pl.DataFrame,
    field_map: dict[str, tuple[str, type]],
    contract: dict[str, Any],
) -> pl.DataFrame:
    """Renomeia campos PascalCase para snake_case e aplica o contrato Silver.

    Args:
        df: DataFrame bruto com colunas PascalCase.
        field_map: Mapeamento ``{api_name: (silver_col, dtype)}``.
        contract: Dicionário ``{silver_col: pl_type}`` do SILVER_SCHEMAS.

    Returns:
        DataFrame com colunas tipadas conforme o contrato Silver.
    """
    if df.is_empty():
        return df

    # Renomeia campos disponíveis
    for api_name, (silver_col, _dtype) in field_map.items():
        if silver_col not in contract:
            continue
        if api_name in df.columns and api_name != silver_col:
            # Só renomeia se o nome for diferente (evita erro se já for igual)
            df = df.rename({api_name: silver_col})

    # Preenche colunas faltantes com null
    missing_cols = [c for c in contract if c not in df.columns]
    for col in missing_cols:
        df = df.with_columns(pl.lit(None).alias(col))

    # Cast e select na ordem do contrato
    return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])


# ── Transformers ──────────────────────────────────────────────────────────────


class DiscursosPlenarioTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de discursos em plenário.

    O DataFrame de entrada contém campos flat (sem envelopes XML).
    O transformer renomeia PascalCase para snake_case e aplica tipagem estrita.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma discursos de plenário para o contrato Silver.

        Args:
            df: DataFrame bruto da API (colunas PascalCase).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme SILVER_SCHEMAS.
        """
        contract = SILVER_SCHEMAS[DomainType.DISCURSOS_PLENARIO.value]
        return _apply_contract(df, _FIELD_MAP_PLENARIO, contract)


class DiscursosSenadorTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de discursos por senador.

    Os dados chegam do envelope XML-heritage já achatado pelo extrator.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma discursos de senador para o contrato Silver.

        Args:
            df: DataFrame bruto da API (colunas PascalCase).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme SILVER_SCHEMAS.
        """
        contract = SILVER_SCHEMAS[DomainType.SENADORES_DISCURSOS.value]
        return _apply_contract(df, _FIELD_MAP_SENADOR, contract)


class DiscursosTextoTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de texto integral de discursos."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma texto integral de discursos para o contrato Silver.

        Args:
            df: DataFrame bruto da API (colunas PascalCase).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme SILVER_SCHEMAS.
        """
        contract = SILVER_SCHEMAS[DomainType.DISCURSOS_TEXTO.value]
        return _apply_contract(df, _FIELD_MAP_TEXTO, contract)


class NotasTaquigrafiaSessaoTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de notas taquigráficas de sessão."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma notas de sessão para o contrato Silver.

        Args:
            df: DataFrame bruto da API (colunas PascalCase).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme SILVER_SCHEMAS.
        """
        contract = SILVER_SCHEMAS[DomainType.NOTAS_TAQUIGRAFIA_SESSAO.value]
        return _apply_contract(df, _FIELD_MAP_SESSAO, contract)


class NotasTaquigrafiaReuniaoTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de notas taquigráficas de reunião."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma notas de reunião para o contrato Silver.

        Args:
            df: DataFrame bruto da API (colunas PascalCase).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme SILVER_SCHEMAS.
        """
        contract = SILVER_SCHEMAS[DomainType.NOTAS_TAQUIGRAFIA_REUNIAO.value]
        return _apply_contract(df, _FIELD_MAP_REUNIAO, contract)
