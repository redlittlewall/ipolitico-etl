"""Extrator do domínio cg_contratos — Contratos do Executivo Federal (API v3).

Página o recurso ``api-de-dados/contratos`` via ``PortalTransparenciaBaseExtractor``.
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


class PortalContratosApiExtractor(PortalTransparenciaBaseExtractor):
    """Extrator de contratos do Poder Executivo Federal via API v3."""

    ENDPOINT = "api-de-dados/contratos"

    async def extract(
        self,
        codigoOrgao: str | None = None,
        dataInicial: str | None = None,
        dataFinal: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Extrai a lista de contratos administrativos com filtros opcionais.

        Args:
            codigoOrgao: Código do órgão SIAFI (opcional).
            dataInicial: Data de início de vigência em DD/MM/AAAA (opcional).
            dataFinal: Data de fim de vigência em DD/MM/AAAA (opcional).
            **kwargs: Argumentos adicionais (ignorados).

        Returns:
            DataFrame bruto com _source_url injetado ou vazio se a API não retornar dados.
        """
        params: dict[str, Any] = {}
        # A API v3 exige codigoOrgao (ex: 26000 - MEC, 36000 - MS).
        params["codigoOrgao"] = codigoOrgao or "26000"

        # Converte ISO YYYY-MM-DD para DD/MM/AAAA se necessário
        dt_ini = dataInicial or kwargs.get("start_date")
        if dt_ini:
            if "-" in str(dt_ini):
                parts = str(dt_ini).split("-")
                dt_ini = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else dt_ini
            params["dataInicial"] = dt_ini

        dt_fim = dataFinal or kwargs.get("end_date")
        if dt_fim:
            if "-" in str(dt_fim):
                parts = str(dt_fim).split("-")
                dt_fim = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else dt_fim
            params["dataFinal"] = dt_fim

        data = await self.fetch_paginated(self.ENDPOINT, params=params)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT, params=params)
