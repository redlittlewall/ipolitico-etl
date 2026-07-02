"""Extratores para os 4 domínios de comissões do Senado.

Endpoints:
- ``/comissao/lista/colegiados`` → COMISSOES_SENADO
- ``/comissao/{codigo}`` → COMISSOES_DETALHE
- ``/comissao/agenda/{inicio}/{fim}`` → COMISSOES_REUNIOES
- ``/composicao/comissao/{codigo}`` → COMISSOES_MEMBROS
"""

import json
import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)


def _serialize_structs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Serializa todos os campos dict aninhados de uma lista de registros como JSON string.

    A API do Senado retorna structs XML-heritage (Cargos, Requerimentos) que
    podem ter formatos inconsistentes entre registros, causando erro de
    ``supertype`` no Polars. Esta função serializa qualquer valor dict (ou
    lista de dicts) para JSON string antes da construçãão do DataFrame.

    Args:
        records: Lista de registros com valores potencialmente aninhados.

    Returns:
        Mesma lista com valores dict/list serializados como JSON string.
    """
    for record in records:
        for key, value in record.items():
            if isinstance(value, (dict, list)):
                record[key] = json.dumps(value, ensure_ascii=False)
    return records


class SenadoComissoesListaExtractor(SenadoBaseExtractor):
    """Extrator da lista de comissões do Senado.

    Chama ``/comissao/lista/colegiados`` e achata o envelope XML-heritage
    para obter o array de colegiados.
    """

    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """Extrai lista de todas as comissões ativas no Senado/Congresso.

        Args:
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos das comissões (Codigo, Sigla, Nome, etc.)
            ou DataFrame vazio se a API não retornar dados.
        """
        raw = await self.fetch_flat("comissao/lista/colegiados")
        records = self.flatten_response(raw, ["ListaColegiados", "Colegiados", "Colegiado"])

        if not records:
            return pl.DataFrame()

        return pl.DataFrame(records, infer_schema_length=None)


class SenadoComissoesDetalheExtractor(SenadoBaseExtractor):
    """Extrator de detalhes de uma ou mais comissões do Senado.

    Chama ``/comissao/{codigo}`` para cada código e achata o envelope
    ``ComissoesCongressoNacional.Colegiados.Colegiado[]``.
    """

    async def extract(
        self,
        entity_ids: list[int] | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai detalhes de uma ou mais comissões pelo código.

        Aceita ``entity_ids`` (lista de códigos, padrão DetailStrategy)
        ou ``codigo_comissao`` (código único, fallback).

        Args:
            entity_ids: Lista de códigos de comissão (ex: [38, 1, 2]).
            **kwargs: Parâmetros adicionais (aceita ``codigo_comissao`` como fallback).

        Returns:
            DataFrame com os dados brutos das comissões (CodigoColegiado,
            NomeColegiado, Cargos struct, etc.) ou DataFrame vazio se
            nenhum código for informado.
        """
        ids = entity_ids
        if not ids:
            single = kwargs.get("codigo_comissao")
            ids = [single] if single is not None else None

        if not ids:
            return pl.DataFrame()

        all_records: list[dict[str, Any]] = []
        for codigo in ids:
            raw = await self.fetch_flat(f"comissao/{codigo}")
            records = self.flatten_response(
                raw, ["ComissoesCongressoNacional", "Colegiados", "Colegiado"]
            )
            all_records.extend(records)

        if not all_records:
            return pl.DataFrame()

        # Serializa structs inconsistentes (Cargos, Requerimentos, etc.) como JSON
        _serialize_structs(all_records)

        return pl.DataFrame(all_records, infer_schema_length=None)


class SenadoComissoesReunioesExtractor(SenadoBaseExtractor):
    """Extrator da agenda de reuniões de comissões do Senado.

    Chama ``/comissao/agenda/{dataInicio}/{dataFim}`` e achata o envelope.
    Aceita datas no formato ``YYYY-MM-DD`` (ISO) e converte internamente para
    ``YYYYMMDD`` no path da URL (exigência da API do Senado).
    """

    async def extract(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai reuniões de comissões dentro de um período.

        Extrai e aplaina ``colegiadoCriador`` (CodigoColegiado, SiglaColegiado,
        NomeColegiado) como colunas planas no DataFrame.

        Args:
            start_date: Data inicial no formato ``YYYY-MM-DD`` (ISO,
                        ex: ``2025-06-01``). Convertida para ``YYYYMMDD`` na URL.
            end_date: Data final no formato ``YYYY-MM-DD`` (ISO,
                      ex: ``2025-06-30``). Convertida para ``YYYYMMDD`` na URL.
            **kwargs: Parâmetros adicionais (aceita ``dataInicio``/``dataFim``
                      como fallback).

        Returns:
            DataFrame com os dados brutos das reuniões, com colunas planas
            e structs aplainadas, ou DataFrame vazio se a API não retornar dados.
        """
        di = start_date or kwargs.get("dataInicio")
        df = end_date or kwargs.get("dataFim")
        if not di or not df:
            return pl.DataFrame()

        # API do Senado espera YYYYMMDD no path da URL (sem hífens)
        raw = await self.fetch_flat(
            f"comissao/agenda/{di.replace('-', '')}/{df.replace('-', '')}",
        )
        records = self.flatten_response(raw, ["AgendaReuniao", "reunioes", "reuniao"])

        if not records:
            return pl.DataFrame()

        # Aplaina colegiadoCriador como colunas prefixadas
        for record in records:
            cc = record.pop("colegiadoCriador", None) or {}
            record["CodigoColegiado"] = cc.get("codigo")
            record["SiglaColegiado"] = cc.get("sigla")
            record["NomeColegiado"] = cc.get("nome")

        # Serializa structs inconsistentes restantes como JSON
        _serialize_structs(records)

        return pl.DataFrame(records, infer_schema_length=None)


class SenadoComissoesMembrosExtractor(SenadoBaseExtractor):
    """Extrator da composição de membros de comissões do Senado.

    Chama ``/composicao/comissao/{codigo}?ativas=S`` para cada comissão
    e combina os dados de ``IdentificacaoComissao`` com cada ``Membro``.
    """

    async def extract(
        self,
        entity_ids: list[int] | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai membros ativos de uma ou mais comissões.

        Aceita ``entity_ids`` (lista de códigos, padrão DetailStrategy)
        ou ``codigo_comissao`` (código único, fallback).

        Para cada comissão, combina ``IdentificacaoComissao[0]`` com
        cada membro da lista, produzindo registros mesclados.

        Args:
            entity_ids: Lista de códigos de comissão (ex: [38, 1, 2]).
            **kwargs: Parâmetros adicionais (aceita ``codigo_comissao`` como fallback).

        Returns:
            DataFrame com dados da comissão + membros, ou DataFrame vazio
            se nenhum código for informado.
        """
        ids = entity_ids
        if not ids:
            single = kwargs.get("codigo_comissao")
            ids = [single] if single is not None else None

        if not ids:
            return pl.DataFrame()

        all_records: list[dict[str, Any]] = []
        for codigo in ids:
            raw = await self.fetch_flat(
                f"composicao/comissao/{codigo}",
                params={"ativas": "S"},
            )

            if not isinstance(raw, dict):
                continue

            composicao = raw.get("ComposicaoAtivaComissaoSf", {}).get("ComposicaoComissao", {})

            identificacao_list = composicao.get("IdentificacaoComissao", [])
            if not identificacao_list:
                continue

            identificacao = self._ensure_list(identificacao_list)[0]
            membros = composicao.get("Membros", {}).get("Membro", [])
            if not membros:
                continue

            # Adiciona dados da comissão a cada membro
            for m in membros:
                m["CodigoComissao"] = identificacao.get("CodigoComissao")
                m["SiglaComissao"] = identificacao.get("SiglaComissao")
                m["NomeComissao"] = identificacao.get("NomeComissao")

            all_records.extend(membros)

        if not all_records:
            return pl.DataFrame()

        return pl.DataFrame(all_records, infer_schema_length=None)
