"""Extrator do domínio cg_cepim — Entidades Sem Fins Lucrativos Impedidas (API v3).

Página o recurso ``api-de-dados/cepim`` via ``PortalTransparenciaBaseExtractor``
com walk livre (sem filtro obrigatório). Devolve o raw da API com ``_source_url``
injetado por página para auditoria replayável.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.extractors.portal_transparencia.api.base_extractor import (
    PortalTransparenciaBaseExtractor,
)


class PortalCepimApiExtractor(PortalTransparenciaBaseExtractor):
    """Extrator do snapshot de entidades sem fins lucrativos impedidas (CEPIM) via API v3."""

    ENDPOINT = "api-de-dados/cepim"

    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """
        Extrai a lista completa paginada do CEPIM.

        Args:
            **kwargs: Argumentos adicionais (ignorados).

        Returns:
            DataFrame bruto com _source_url injetado ou vazio se a API não retornar dados.
        """
        data = await self.fetch_paginated(self.ENDPOINT)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT)
