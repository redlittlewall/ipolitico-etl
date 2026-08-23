"""Extrator do domínio cg_convenios_aditivos — Termos Aditivos de Convênios (API v3).

Consulta e página o recurso ``api-de-dados/convenios`` via
``PortalTransparenciaBaseExtractor`` para obtenção de termos aditivos de
convênios. Devolve o raw da API com ``_source_url`` injetado por página para
auditoria replayável.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.extractors.portal_transparencia.api.base_extractor import (
    PortalTransparenciaBaseExtractor,
)


class PortalConveniosAditivosApiExtractor(PortalTransparenciaBaseExtractor):
    """Extrator de termos aditivos de convênios via API v3."""

    ENDPOINT = "api-de-dados/convenios"

    async def extract(
        self,
        numero: str | None = None,
        id: int | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Extrai termos aditivos de convênios.

        Args:
            numero: Número do convênio (opcional).
            id: ID do registro de convênio (opcional).
            **kwargs: Argumentos adicionais (ignorados).

        Returns:
            DataFrame bruto com _source_url injetado ou vazio se a API não retornar dados.
        """
        params: dict[str, Any] = {}
        if numero is not None:
            params["numero"] = numero
        if id is not None:
            params["id"] = id

        query_params = params if params else None
        data = await self.fetch_paginated(self.ENDPOINT, params=query_params)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT, params=query_params)
