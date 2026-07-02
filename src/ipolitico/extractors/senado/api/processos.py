"""Extratores para os domínios de processos legislativos do Senado.

Inclui:
- ``SenadoProcessosExtractor`` — lista de processos (``/processo``)
- ``SenadoProcessosDetalheExtractor`` — detalhes por ID (``/processo/{id}``)
- ``SenadoProcessosEmendasExtractor`` — emendas (``/processo/emenda``)
- ``SenadoProcessosDocumentosExtractor`` — documentos (``/processo/documento``)
"""

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.senado.api.senado_base import SenadoBaseExtractor

logger = logging.getLogger(__name__)


class SenadoProcessosExtractor(SenadoBaseExtractor):
    """Extrator de processos legislativos do Senado.

    Chama ``/processo`` que retorna um array flat (sem envelope XML).
    O endpoint não aceita filtro temporal — retorna todo o acervo (~10K registros).
    """

    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """Extrai a lista completa de processos.

        Args:
            **kwargs: Parâmetros adicionais (start_date/end_date são aceitos
                      mas ignorados — a API não suporta filtro temporal).

        Returns:
            DataFrame com os dados brutos dos processos.
        """
        raw = await self.fetch_flat("processo")

        if not raw or not isinstance(raw, list):
            return pl.DataFrame()

        df = pl.DataFrame(raw, infer_schema_length=None)
        return self._inject_source_url(df, "processo")


class SenadoProcessosDetalheExtractor(SenadoBaseExtractor):
    """Extrator de detalhes de um processo legislativo.

    Chama ``/processo/{id}`` que retorna um dict com dados detalhados
    do processo (incluindo conteúdo, documento, tramitação etc.).
    """

    async def extract(
        self,
        entity_ids: list[int] | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai detalhes de um ou mais processos.

        Args:
            entity_ids: Lista de IDs de processo. Se vazio, retorna DataFrame vazio.
            **kwargs: Parâmetros adicionais (ignorados).

        Returns:
            DataFrame com os dados brutos dos detalhes dos processos.
        """
        if not entity_ids:
            return pl.DataFrame()

        all_dfs: list[pl.DataFrame] = []
        for pid in entity_ids:
            raw = await self.fetch_flat(f"processo/{pid}")
            if isinstance(raw, dict):
                df = pl.DataFrame([raw], infer_schema_length=None)
                df = self._inject_source_url(df, f"processo/{pid}")
                all_dfs.append(df)

        if not all_dfs:
            return pl.DataFrame()

        return pl.concat(all_dfs)


class SenadoProcessosEmendasExtractor(SenadoBaseExtractor):
    """Extrator de emendas a processos legislativos.

    Chama ``/processo/emenda`` com parâmetros ``dataInicio``/``dataFim``
    (janela mensal) e retorna um array flat.
    """

    async def extract(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai emendas dentro de uma janela temporal.

        Args:
            start_date: Data inicial no formato ``YYYY-MM-DD``.
            end_date: Data final no formato ``YYYY-MM-DD``.
            **kwargs: Parâmetros adicionais (aceita ``dataInicio``/``dataFim``
                      como fallback para compatibilidade com o orquestrador).

        Returns:
            DataFrame com os dados brutos das emendas.
        """
        params: dict[str, str] = {}
        di = start_date or kwargs.get("dataInicio")
        df = end_date or kwargs.get("dataFim")
        if di:
            params["dataInicio"] = di
        if df:
            params["dataFim"] = df

        raw = await self.fetch_flat("processo/emenda", params=params or None)

        if not raw or not isinstance(raw, list):
            return pl.DataFrame()

        df = pl.DataFrame(raw, infer_schema_length=None)
        return self._inject_source_url(df, "processo/emenda", params=params or None)


class SenadoProcessosDocumentosExtractor(SenadoBaseExtractor):
    """Extrator de documentos de processos legislativos.

    Chama ``/processo/documento`` com parâmetros ``dataInicio``/``dataFim``
    (janela mensal) e retorna um array flat.
    """

    async def extract(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai documentos dentro de uma janela temporal.

        Args:
            start_date: Data inicial no formato ``YYYY-MM-DD``.
            end_date: Data final no formato ``YYYY-MM-DD``.
            **kwargs: Parâmetros adicionais (aceita ``dataInicio``/``dataFim``
                      como fallback para compatibilidade com o orquestrador).

        Returns:
            DataFrame com os dados brutos dos documentos.
        """
        params: dict[str, str] = {}
        di = start_date or kwargs.get("dataInicio")
        df = end_date or kwargs.get("dataFim")
        if di:
            params["dataInicio"] = di
        if df:
            params["dataFim"] = df

        raw = await self.fetch_flat("processo/documento", params=params or None)

        if not raw or not isinstance(raw, list):
            return pl.DataFrame()

        df = pl.DataFrame(raw, infer_schema_length=None)
        return self._inject_source_url(df, "processo/documento", params=params or None)
