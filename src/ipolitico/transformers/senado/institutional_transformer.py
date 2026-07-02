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


# ── Plenário (Issue 08b) ──────────────────────────────────────────────────────

_PLENARIO_AGENDA_FIELD_MAP: dict[str, tuple[str, type]] = {
    "CodigoSessao": ("codigo_sessao", pl.Int64),
    "Data": ("data", pl.String),
    "DiaSemana": ("dia_semana", pl.String),
    "Hora": ("hora", pl.String),
    "NumeroSessao": ("numero_sessao", pl.String),
    "TipoSessao": ("tipo_sessao", pl.String),
    "LocalSessao": ("local_sessao", pl.String),
    "Casa": ("casa", pl.String),
    "SessaoLegislativa": ("sessao_legislativa", pl.String),
    "Legislatura": ("legislatura", pl.String),
    "CodigoSituacaoSessao": ("codigo_situacao_sessao", pl.Int64),
    "SituacaoSessao": ("situacao_sessao", pl.String),
    "Realizada": ("realizada", pl.String),
    "PautaConfirmada": ("pauta_confirmada", pl.String),
    "TipoPresenca": ("tipo_presenca", pl.String),
    "DescricaoTipoPresenca": ("descricao_tipo_presenca", pl.String),
    "Evento": ("evento", pl.String),
    "Oradores": ("oradores", pl.String),
}

_PLENARIO_RESULTADOS_FIELD_MAP: dict[str, tuple[str, type]] = {
    "codigoSessao": ("codigo_sessao", pl.String),
    "codigoItem": ("codigo_item", pl.String),
    "codigoMateria": ("codigo_materia", pl.String),
    "idIdentificacao": ("id_identificacao", pl.String),
    "identificacao": ("identificacao", pl.String),
    "parecer": ("parecer", pl.String),
    "ementaPapeleta": ("ementa_papeleta", pl.String),
    "siglaCasaMateria": ("sigla_casa_materia", pl.String),
    "siglaMateria": ("sigla_materia", pl.String),
    "numeroMateria": ("numero_materia", pl.String),
    "anoMateria": ("ano_materia", pl.String),
    "DescricaoIdentificacaoMateria": ("descricao_identificacao_materia", pl.String),
    "textoResultado": ("texto_resultado", pl.String),
    "indicadorDeliberacao": ("indicador_deliberacao", pl.String),
    "descricaoDeliberacao": ("descricao_deliberacao", pl.String),
    "sequencialItem": ("sequencial_item", pl.String),
    "tipoPauta": ("tipo_pauta", pl.String),
    "descricaoTipoPauta": ("descricao_tipo_pauta", pl.String),
    "indicadorRevisado": ("indicador_revisado", pl.String),
    "codigoTipoApreciacao": ("codigo_tipo_apreciacao", pl.String),
    "descricaoTipoApreciacao": ("descricao_tipo_apreciacao", pl.String),
    "autorMateria": ("autor_materia", pl.String),
    "dataSessao": ("data_sessao", pl.String),
    "siglaCasa": ("sigla_casa", pl.String),
}

_PLENARIO_SESSOES_FIELD_MAP: dict[str, tuple[str, type]] = {
    "NumeroLegislatura": ("numero_legislatura", pl.Int64),
    "NumeroSessaoLegislativa": ("numero_sessao_legislativa", pl.Int64),
    "TipoSessaoLegislativa": ("tipo_sessao_legislativa", pl.String),
    "DataInicio": ("data_inicio", pl.String),
    "DataFim": ("data_fim", pl.String),
    "DataEleicao": ("data_eleicao", pl.String),
    "DataInicioLegislatura": ("data_inicio_legislatura", pl.String),
    "DataFimLegislatura": ("data_fim_legislatura", pl.String),
}


class PlenarioAgendaTransformer(BaseTransformer):
    """Aplica contrato Silver à agenda do plenário do Senado.

    Serializa structs (Evento, Oradores) como JSON string e renomeia
    campos PascalCase para snake_case.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma DataFrame bruto da agenda do plenário.

        Args:
            df: DataFrame com colunas da API (CodigoSessao, Data, Hora, ...).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame no schema Silver de ``plenario_agenda``.
        """
        return _apply_senado_contract(
            df, _PLENARIO_AGENDA_FIELD_MAP, DomainType.PLENARIO_AGENDA.value
        )


class PlenarioResultadosTransformer(BaseTransformer):
    """Aplica contrato Silver aos resultados de votações em plenário."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma DataFrame bruto dos resultados de votações.

        Args:
            df: DataFrame com colunas da API (codigoItem, codigoMateria, ...).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame no schema Silver de ``plenario_resultados``.
        """
        return _apply_senado_contract(
            df, _PLENARIO_RESULTADOS_FIELD_MAP, DomainType.PLENARIO_RESULTADOS.value
        )


class PlenarioSessoesTransformer(BaseTransformer):
    """Aplica contrato Silver às sessões legislativas do Senado.

    Cada linha corresponde a uma SessaoLegislativa dentro de uma
    Legislatura, com metadados da legislatura (NumeroLegislatura,
    DataEleicao, etc.)
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma DataFrame bruto das sessões legislativas.

        Args:
            df: DataFrame com colunas da API (NumeroSessaoLegislativa,
                TipoSessaoLegislativa, DataInicio, ...).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame no schema Silver de ``plenario_sessoes``.
        """
        return _apply_senado_contract(
            df, _PLENARIO_SESSOES_FIELD_MAP, DomainType.PLENARIO_SESSOES.value
        )


# ── Composição (Issue 08c) ─────────────────────────────────────────────────────

_BLOCOS_SENADO_FIELD_MAP: dict[str, tuple[str, type]] = {
    "CodigoBloco": ("codigo", pl.Int64),
    "NomeBloco": ("nome", pl.String),
    "NomeApelido": ("nome_apelido", pl.String),
    "DataCriacao": ("data_criacao", pl.String),
    "Membros": ("membros", pl.String),
}

_LIDERANCAS_SENADO_FIELD_MAP: dict[str, tuple[str, type]] = {
    "codigo": ("codigo", pl.Int64),
    "casa": ("casa", pl.String),
    "idTipoUnidadeLideranca": ("id_tipo_unidade_lideranca", pl.Int64),
    "siglaTipoUnidadeLideranca": ("sigla_tipo_unidade_lideranca", pl.String),
    "descricaoTipoUnidadeLideranca": ("descricao_tipo_unidade_lideranca", pl.String),
    "codigoParlamentar": ("codigo_parlamentar", pl.Int64),
    "nomeParlamentar": ("nome_parlamentar", pl.String),
    "dataDesignacao": ("data_designacao", pl.String),
    "dataTermino": ("data_termino", pl.String),
    "siglaTipoLideranca": ("sigla_tipo_lideranca", pl.String),
    "descricaoTipoLideranca": ("descricao_tipo_lideranca", pl.String),
    "numeroOrdemViceLider": ("numero_ordem_vice_lider", pl.Int64),
    "codigoBloco": ("codigo_bloco", pl.Int64),
    "siglaBloco": ("sigla_bloco", pl.String),
    "nomeBloco": ("nome_bloco", pl.String),
    "codigoPartido": ("codigo_partido", pl.Int64),
    "siglaPartido": ("sigla_partido", pl.String),
    "nomePartido": ("nome_partido", pl.String),
    "codigoPartidoFiliacao": ("codigo_partido_filiacao", pl.Int64),
    "siglaPartidoFiliacao": ("sigla_partido_filiacao", pl.String),
    "nomePartidoFiliacao": ("nome_partido_filiacao", pl.String),
}

_MESA_SENADO_FIELD_MAP: dict[str, tuple[str, type]] = {
    "CodigoColegiado": ("codigo_colegiado", pl.Int64),
    "NomeColegiado": ("nome_colegiado", pl.String),
    "SiglaColegiado": ("sigla_colegiado", pl.String),
    "Cargo": ("cargo", pl.String),
    "NomeParlamentar": ("nome_parlamentar", pl.String),
    "Bancada": ("bancada", pl.String),
    "Http": ("codigo_parlamentar", pl.Int64),
    "NumeroOrdemImpressao": ("numero_ordem_impressao", pl.String),
    "Origem": ("origem", pl.String),
}

_MESA_CONGRESSO_FIELD_MAP: dict[str, tuple[str, type]] = {
    "CodigoColegiado": ("codigo_colegiado", pl.Int64),
    "NomeColegiado": ("nome_colegiado", pl.String),
    "SiglaColegiado": ("sigla_colegiado", pl.String),
    "TipoCargo": ("tipo_cargo", pl.String),
    "CodigoCargo": ("codigo_cargo", pl.String),
    "NomeParlamentar": ("nome_parlamentar", pl.String),
    "CodigoParlamentar": ("codigo_parlamentar", pl.String),
    "Bancada": ("bancada", pl.String),
    "CodigoDeputadoNaCamara": ("codigo_deputado_camara", pl.String),
}


class BlocosSenadoTransformer(BaseTransformer):
    """Aplica contrato Silver à lista de blocos parlamentares do Senado.

    O campo ``Membros`` já vem serializado como JSON string pelo extrator.
    """

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma DataFrame bruto dos blocos parlamentares.

        Args:
            df: DataFrame com colunas da API (CodigoBloco, NomeBloco, ...).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame no schema Silver de ``blocos_senado``.
        """
        return _apply_senado_contract(df, _BLOCOS_SENADO_FIELD_MAP, DomainType.BLOCOS_SENADO.value)


class LiderancasSenadoTransformer(BaseTransformer):
    """Aplica contrato Silver à lista de lideranças do Senado."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma DataFrame bruto das lideranças.

        Args:
            df: DataFrame com colunas da API (codigo, casa,
                codigoParlamentar, nomeParlamentar, ...).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame no schema Silver de ``liderancas_senado``.
        """
        return _apply_senado_contract(
            df, _LIDERANCAS_SENADO_FIELD_MAP, DomainType.LIDERANCAS_SENADO.value
        )


class MesaSenadoTransformer(BaseTransformer):
    """Aplica contrato Silver à composição da mesa diretora do Senado."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma DataFrame bruto da mesa do Senado.

        Cada linha corresponde a um cargo dentro de um colegiado,
        com metadados do colegiado anexados.

        Args:
            df: DataFrame com colunas da API (CodigoColegiado, Cargo,
                NomeParlamentar, Bancada, ...).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame no schema Silver de ``mesa_senado``.
        """
        return _apply_senado_contract(df, _MESA_SENADO_FIELD_MAP, DomainType.MESA_SENADO.value)


class MesaCongressoTransformer(BaseTransformer):
    """Aplica contrato Silver à composição da mesa diretora do Congresso."""

    def transform(self, df: pl.DataFrame, **kwargs: Any) -> pl.DataFrame:
        """Transforma DataFrame bruto da mesa do Congresso.

        Cada linha corresponde a um cargo dentro de um colegiado,
        com metadados do colegiado anexados.

        Args:
            df: DataFrame com colunas da API (CodigoColegiado, TipoCargo,
                NomeParlamentar, Bancada, ...).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame no schema Silver de ``mesa_congresso``.
        """
        return _apply_senado_contract(
            df, _MESA_CONGRESSO_FIELD_MAP, DomainType.MESA_CONGRESSO.value
        )
