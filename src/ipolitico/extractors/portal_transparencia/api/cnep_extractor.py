"""Extrator do domínio cg_cnep — Cadastro Nacional de Empresas Punidas (API v3).

Página o recurso ``api-de-dados/cnep`` via ``PortalTransparenciaBaseExtractor``
com walk livre (sem filtro obrigatório). Devolve o raw da API com ``_source_url``
injetado por página para auditoria replayável.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.extractors.portal_transparencia.api.base_extractor import (
    PortalTransparenciaBaseExtractor,
)


class PortalCnepApiExtractor(PortalTransparenciaBaseExtractor):
    """Extrator do snapshot de empresas punidas (CNEP - Lei Anticorrupção) via API v3."""

    ENDPOINT = "api-de-dados/cnep"

    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """
        Extrai a lista completa paginada do CNEP.

        Args:
            **kwargs: Argumentos adicionais (ignorados).

        Returns:
            DataFrame bruto com _source_url injetado ou vazio se a API não retornar dados.
        """
        data = await self.fetch_paginated(self.ENDPOINT)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT)
