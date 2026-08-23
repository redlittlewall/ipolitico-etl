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
        # A API v3 exige codigoOrgao (ex: 26000 - MEC, 36000 - MS).
        params["codigoOrgao"] = codigoOrgao or "26000"

        # Apenas envia período se informado explicitamente (evita 400 por janela > 1 mês na consulta histórica)
        dt_ini = dataInicial or (kwargs.get("start_date") if kwargs.get("start_date") != "1826-04-29" else None)
        if dt_ini:
            if "-" in str(dt_ini):
                parts = str(dt_ini).split("-")
                dt_ini = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else dt_ini
            params["dataInicial"] = dt_ini

        dt_fim = dataFinal or (kwargs.get("end_date") if kwargs.get("start_date") != "1826-04-29" else None)
        if dt_fim and dt_ini:
            if "-" in str(dt_fim):
                parts = str(dt_fim).split("-")
                dt_fim = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else dt_fim
            params["dataFinal"] = dt_fim

        data = await self.fetch_paginated(self.ENDPOINT, params=params)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT, params=params)
