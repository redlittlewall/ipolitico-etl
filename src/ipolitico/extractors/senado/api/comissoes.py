"""Extratores para os 4 domínios de comissões do Senado.

Endpoints:
- ``/comissao/lista/colegiados`` → COMISSOES_SENADO
- ``/comissao/{codigo}`` → COMISSOES_DETALHE
- ``/comissao/agenda/{inicio}/{fim}`` → COMISSOES_REUNIOES
- ``/composicao/comissao/{codigo}`` → COMISSOES_MEMBROS
"""

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)


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
    """Extrator de detalhes de uma comissão do Senado.

    Chama ``/comissao/{codigo}`` e achata o envelope para obter o
    array de colegiado (tipicamente 1 elemento).
    """

    async def extract(
        self,
        codigo_comissao: int | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai detalhes de uma comissão pelo código.

        Args:
            codigo_comissao: Código numérico da comissão (ex: 38 para CAE).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos da comissão (CodigoColegiado,
            NomeColegiado, Cargos struct, etc.) ou DataFrame vazio se o
            código não for informado ou a comissão não existir.
        """
        codigo = codigo_comissao or kwargs.get("codigo_comissao")
        if codigo is None:
            return pl.DataFrame()

        raw = await self.fetch_flat(f"comissao/{codigo}")
        records = self.flatten_response(
            raw, ["ComissoesCongressoNacional", "Colegiados", "Colegiado"]
        )

        if not records:
            return pl.DataFrame()

        return pl.DataFrame(records, infer_schema_length=None)


class SenadoComissoesReunioesExtractor(SenadoBaseExtractor):
    """Extrator da agenda de reuniões de comissões do Senado.

    Chama ``/comissao/agenda/{dataInicio}/{dataFim}`` e achata o envelope.
    As datas devem estar no formato ``YYYYMMDD``.
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
            start_date: Data inicial no formato ``YYYYMMDD`` (ex: ``20250601``).
            end_date: Data final no formato ``YYYYMMDD`` (ex: ``20250630``).
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

        raw = await self.fetch_flat(
            f"comissao/agenda/{di}/{df}",
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

        return pl.DataFrame(records, infer_schema_length=None)


class SenadoComissoesMembrosExtractor(SenadoBaseExtractor):
    """Extrator da composição de membros de comissões do Senado.

    Chama ``/composicao/comissao/{codigo}?ativas=S`` e combina os dados
    de ``IdentificacaoComissao`` com cada ``Membro``.
    """

    async def extract(
        self,
        codigo_comissao: int | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai membros ativos de uma comissão.

        Combina ``IdentificacaoComissao[0]`` com cada membro da lista,
        produzindo registros com dados da comissão + membro.

        Args:
            codigo_comissao: Código numérico da comissão (ex: 38 para CAE).
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com dados da comissão + membros, ou DataFrame vazio
            se o código não for informado ou a comissão não existir.
        """
        codigo = codigo_comissao or kwargs.get("codigo_comissao")
        if codigo is None:
            return pl.DataFrame()

        raw = await self.fetch_flat(
            f"composicao/comissao/{codigo}",
            params={"ativas": "S"},
        )

        if not isinstance(raw, dict):
            return pl.DataFrame()

        composicao = raw.get("ComposicaoAtivaComissaoSf", {}).get("ComposicaoComissao", {})

        identificacao_list = composicao.get("IdentificacaoComissao", [])
        if not identificacao_list:
            return pl.DataFrame()

        identificacao = self._ensure_list(identificacao_list)[0]
        membros = composicao.get("Membros", {}).get("Membro", [])
        if not membros:
            return pl.DataFrame()

        # Adiciona dados da comissão a cada membro
        for m in membros:
            m["CodigoComissao"] = identificacao.get("CodigoComissao")
            m["SiglaComissao"] = identificacao.get("SiglaComissao")
            m["NomeComissao"] = identificacao.get("NomeComissao")

        return pl.DataFrame(membros, infer_schema_length=None)
