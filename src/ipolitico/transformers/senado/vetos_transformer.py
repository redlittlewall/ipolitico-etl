"""Transformadores para os domínios de vetos presidenciais — mapeia campos flat do novo envelope.

A API agora retorna objetos aninhados (Materia, MateriaVetada, Mensagem) que são
aplainados em chaves ``_`` pelo extrator. O transformer renomeia para snake_case
e aplica tipagem estrita conforme o contrato Silver.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.core.constants import DomainType
from ipolitico.core.schemas import SILVER_SCHEMAS
from ipolitico.transformers.base import BaseTransformer

# Mapeamento dos campos flat da API → colunas Silver para vetos_presidenciais
# Inclui campos da raiz do Veto + campos aplainados de Materia, MateriaVetada
# (incluindo NormaGerada), e Mensagem.
_FIELD_MAP_PRESIDENCIAIS: dict[str, tuple[str, type]] = {
    # ── Flat ──────────────────────────────────────────────────────────────────
    "Codigo": ("codigo", pl.Int64),
    "Total": ("total", pl.String),
    "Assunto": ("assunto", pl.String),
    "DataRecebimentoCongresso": ("data_recebimento_congresso", pl.String),
    "DataPublicacao": ("data_publicacao", pl.String),
    "DataSobrestacaoPauta": ("data_sobrestacao_pauta", pl.String),
    "SobrestandoPauta": ("sobrestando_pauta", pl.String),
    "QuantidadeDispositivos": ("quantidade_dispositivos", pl.Int64),
    "UrlDispositivos": ("url_dispositivos", pl.String),
    # ── Materia ────────────────────────────────────────────────────────────────
    "Materia_Codigo": ("materia_codigo", pl.Int64),
    "Materia_SiglaCasa": ("materia_sigla_casa", pl.String),
    "Materia_NomeCasa": ("materia_nome_casa", pl.String),
    "Materia_Sigla": ("materia_sigla", pl.String),
    "Materia_Numero": ("materia_numero", pl.String),
    "Materia_Ano": ("materia_ano", pl.Int64),
    "Materia_EmTramitacao": ("materia_em_tramitacao", pl.String),
    "Materia_Ementa": ("materia_ementa", pl.String),
    "Materia_UrlMovimentacoes": ("materia_url_movimentacoes", pl.String),
    # ── MateriaVetada ──────────────────────────────────────────────────────────
    "MateriaVetada_Codigo": ("materia_vetada_codigo", pl.Int64),
    "MateriaVetada_SiglaCasa": ("materia_vetada_sigla_casa", pl.String),
    "MateriaVetada_NomeCasa": ("materia_vetada_nome_casa", pl.String),
    "MateriaVetada_Sigla": ("materia_vetada_sigla", pl.String),
    "MateriaVetada_Numero": ("materia_vetada_numero", pl.String),
    "MateriaVetada_Ano": ("materia_vetada_ano", pl.Int64),
    "MateriaVetada_DescricaoObjetivoProcesso": (
        "materia_vetada_descricao_objetivo_processo",
        pl.String,
    ),
    "MateriaVetada_EmTramitacao": ("materia_vetada_em_tramitacao", pl.String),
    "MateriaVetada_Ementa": ("materia_vetada_ementa", pl.String),
    "MateriaVetada_UrlMovimentacoes": ("materia_vetada_url_movimentacoes", pl.String),
    "MateriaVetada_UrlRelatorias": ("materia_vetada_url_relatorias", pl.String),
    # ── MateriaVetada > NormaGerada ────────────────────────────────────────────
    "MateriaVetada_NormaGerada_NomeNorma": (
        "materia_vetada_norma_gerada_nome_norma",
        pl.String,
    ),
    "MateriaVetada_NormaGerada_UrlNorma": (
        "materia_vetada_norma_gerada_url_norma",
        pl.String,
    ),
    "MateriaVetada_NormaGerada_CodigoNorma": (
        "materia_vetada_norma_gerada_codigo_norma",
        pl.Int64,
    ),
    "MateriaVetada_NormaGerada_SiglaTipoNorma": (
        "materia_vetada_norma_gerada_sigla_tipo_norma",
        pl.String,
    ),
    "MateriaVetada_NormaGerada_DescricaoTipoNorma": (
        "materia_vetada_norma_gerada_descricao_tipo_norma",
        pl.String,
    ),
    "MateriaVetada_NormaGerada_NumeroNorma": (
        "materia_vetada_norma_gerada_numero_norma",
        pl.String,
    ),
    "MateriaVetada_NormaGerada_AnoNorma": (
        "materia_vetada_norma_gerada_ano_norma",
        pl.Int64,
    ),
    "MateriaVetada_NormaGerada_DataAssinatura": (
        "materia_vetada_norma_gerada_data_assinatura",
        pl.String,
    ),
    "MateriaVetada_NormaGerada_DataPublicacao": (
        "materia_vetada_norma_gerada_data_publicacao",
        pl.String,
    ),
    "MateriaVetada_NormaGerada_SiglaVeiculoPublicacao": (
        "materia_vetada_norma_gerada_sigla_veiculo_publicacao",
        pl.String,
    ),
    "MateriaVetada_NormaGerada_DescricaoVeiculoPublicacao": (
        "materia_vetada_norma_gerada_descricao_veiculo_publicacao",
        pl.String,
    ),
    # ── Mensagem ───────────────────────────────────────────────────────────────
    "Mensagem_Sigla": ("mensagem_sigla", pl.String),
    "Mensagem_Numero": ("mensagem_numero", pl.String),
    "Mensagem_Ano": ("mensagem_ano", pl.Int64),
    "Mensagem_UrlPlanalto": ("mensagem_url_planalto", pl.String),
}

# Mapeamento dos campos flat da API → colunas Silver para vetos_detalhe.
# Mesmo mapeamento que vetos_presidenciais + Dispositivos como JSON string.
_FIELD_MAP_DETALHE: dict[str, tuple[str, type]] = {
    **_FIELD_MAP_PRESIDENCIAIS,
    "Dispositivos": ("dispositivos", pl.String),
}


class VetosPresidenciaisTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de vetos presidenciais.

    O DataFrame de entrada contém campos flat (sem envelopes XML) com campos
    aninhados já aplainados pelo extrator. O transformer renomeia para
    snake_case e aplica tipagem estrita.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma o DataFrame bruto de vetos presidenciais para o contrato Silver.

        Args:
            df: DataFrame bruto da API (colunas PascalCase com prefixos ``_``
                para campos aninhados aplainados).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme SILVER_SCHEMAS.
            Retorna DataFrame vazio se a entrada for vazia.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.VETOS_PRESIDENCIAIS.value]

        # ── Renomeia e tipa campos disponíveis ──────────────────────────────
        for api_name, (silver_col, _dtype) in _FIELD_MAP_PRESIDENCIAIS.items():
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                df = df.rename({api_name: silver_col})

        # ── Cast dos campos do contrato ─────────────────────────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])


class VetosDetalheTransformer(BaseTransformer):
    """Aplica contrato Silver ao DataFrame bruto de detalhes de veto.

    Mesmo mapeamento de campos que o transformer de presidenciais, mas com
    coluna adicional ``dispositivos`` (JSON string) para os itens vetados.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma o DataFrame bruto de detalhes de veto para o contrato Silver.

        Args:
            df: DataFrame bruto da API (colunas PascalCase com prefixos).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com colunas snake_case tipadas conforme SILVER_SCHEMAS.
            Retorna DataFrame vazio se a entrada for vazia.
        """
        if df.is_empty():
            return df

        contract = SILVER_SCHEMAS[DomainType.VETOS_DETALHE.value]

        # ── Renomeia e tipa campos disponíveis ──────────────────────────────
        for api_name, (silver_col, _dtype) in _FIELD_MAP_DETALHE.items():
            if silver_col not in contract:
                continue
            if api_name in df.columns:
                df = df.rename({api_name: silver_col})

        # ── Cast dos campos do contrato ─────────────────────────────────────
        missing_cols = [c for c in contract if c not in df.columns]
        for col in missing_cols:
            df = df.with_columns(pl.lit(None).alias(col))

        return df.select([pl.col(c).cast(contract[c], strict=False) for c in contract])
