"""Extrator do domínio cg_despesas_pagamentos — Documentos de Pagamento (API v3).

Página o recurso ``api-de-dados/despesas/documentos`` via
``PortalTransparenciaBaseExtractor`` fixando ``fase=3`` (Pagamento).
Suporta parâmetros de data de emissão (``dataEmissao``), unidade gestora
(``unidadeGestora``) e gestão (``gestao``). Devolve o raw da API com
``_source_url`` injetado por página para auditoria replayável.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.extractors.portal_transparencia.api.base_extractor import (
    PortalTransparenciaBaseExtractor,
)


class PortalDespesasPagamentosApiExtractor(PortalTransparenciaBaseExtractor):
    """Extrator de documentos de pagamento de despesas federais via API v3."""

    ENDPOINT = "api-de-dados/despesas/documentos"

    async def extract(
        self,
        dataEmissao: str | None = None,
        unidadeGestora: str | None = None,
        gestao: str | None = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Extrai documentos de pagamento (fase 3) com filtros opcionais.

        Args:
            dataEmissao: Data de emissão em DD/MM/AAAA (opcional).
            unidadeGestora: Código da UG SIAFI (opcional).
            gestao: Código da gestão SIAFI (opcional).
            **kwargs: Argumentos adicionais (ignorados).

        Returns:
            DataFrame bruto com _source_url injetado ou vazio se a API não retornar dados.
        """
        params: dict[str, Any] = {"fase": 3}
        if dataEmissao:
            params["dataEmissao"] = dataEmissao
        if unidadeGestora:
            params["unidadeGestora"] = unidadeGestora
        if gestao:
            params["gestao"] = gestao

        data = await self.fetch_paginated(self.ENDPOINT, params=params)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT, params=params)
