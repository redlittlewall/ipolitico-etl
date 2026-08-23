"""Extrator do domínio cg_contratos_aditivos — Termos Aditivos de Contratos (API v3).

Consulta o recurso ``api-de-dados/contratos/termo-aditivo`` via
``PortalTransparenciaBaseExtractor``. Suporta consulta por ID de contrato
(``id``) ou paginação. Devolve o raw da API com ``_source_url`` injetado por
página para auditoria replayável.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.extractors.portal_transparencia.api.base_extractor import (
    PortalTransparenciaBaseExtractor,
)


class PortalContratosAditivosApiExtractor(PortalTransparenciaBaseExtractor):
    """Extrator de termos aditivos de contratos via API v3."""

    ENDPOINT = "api-de-dados/contratos/termo-aditivo"

    async def extract(
        self,
        id: int | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Extrai os termos aditivos de contrato.

        Args:
            id: ID do contrato (opcional).
            **kwargs: Argumentos adicionais (ignorados).

        Returns:
            DataFrame bruto com _source_url injetado ou vazio se a API não retornar dados.
        """
        params: dict[str, Any] = {}
        if id is not None:
            params["id"] = id

        query_params = params if params else None
        data = await self.fetch_paginated(self.ENDPOINT, params=query_params)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT, params=query_params)
