"""Extrator do domínio cg_licitacoes — Licitações do Executivo Federal (API v3).

Página o recurso ``api-de-dados/licitacoes`` via ``PortalTransparenciaBaseExtractor``.
Suporta parâmetros opcionais (``codigoOrgao``, ``dataInicial``, ``dataFinal``) ou
walk livre por página. Devolve o raw da API com ``_source_url`` injetado por
página para auditoria replayável.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.extractors.portal_transparencia.api.base_extractor import (
    PortalTransparenciaBaseExtractor,
)


class PortalLicitacoesApiExtractor(PortalTransparenciaBaseExtractor):
    """Extrator de licitações do Poder Executivo Federal via API v3."""

    ENDPOINT = "api-de-dados/licitacoes"

    async def extract(
        self,
        codigoOrgao: str | None = None,
        dataInicial: str | None = None,
        dataFinal: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Extrai a lista de licitações com filtros opcionais.

        Args:
            codigoOrgao: Código do órgão SIAFI (opcional).
            dataInicial: Data de abertura inicial em DD/MM/AAAA (opcional).
            dataFinal: Data de abertura final em DD/MM/AAAA (opcional).
            **kwargs: Argumentos adicionais (ignorados).

        Returns:
            DataFrame bruto com _source_url injetado ou vazio se a API não retornar dados.
        """
        params: dict[str, Any] = {}
        if codigoOrgao:
            params["codigoOrgao"] = codigoOrgao
        if dataInicial:
            params["dataInicial"] = dataInicial
        if dataFinal:
            params["dataFinal"] = dataFinal

        query_params = params if params else None
        data = await self.fetch_paginated(self.ENDPOINT, params=query_params)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT, params=query_params)
