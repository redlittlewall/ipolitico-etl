"""Extrator do domínio cg_orgaos — snapshot de órgãos SIAPE (API v3).

Correção de fonte do ticket 02: o portal NÃO tem módulo bulk de órgãos
(``/download-de-dados/orgaos`` responde HTTP 500 — módulo inexistente), então o
domínio é consumido pela API v3 ``/api-de-dados/orgaos-siape`` (contrato
``codigo``/``descricao``, 640 registros, page_size fixo em 15). Estabelece o
padrão de extrator API-first do portal — necessário também para ``orgaos-siafi``
e as consultas agregadas ``por-orgao``.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.extractors.portal_transparencia.api.base_extractor import (
    PortalTransparenciaBaseExtractor,
)


class PortalOrgaosApiExtractor(PortalTransparenciaBaseExtractor):
    """
    Extrator do snapshot de órgãos SIAPE do Poder Executivo (API v3).

    Página o recurso ``api-de-dados/orgaos-siape`` até esgotar e injeta
    ``_source_url`` por página (``...?pagina=N``) para auditoria replayável.
    Devolve o raw como veio da API (colunas String — a tipagem estrita vive no
    transformer), sem aplicar regras de negócio.
    """

    ENDPOINT = "api-de-dados/orgaos-siape"

    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """
        Extrai o snapshot de órgãos SIAPE (lista paginada completa).

        Args:
            **kwargs: Argumentos adicionais (ignorados — snapshot sem janela).

        Returns:
            DataFrame bruto com colunas ``codigo``/``descricao`` (String) e
            ``_source_url`` por linha apontando para a página de origem.
            DataFrame vazio se a API não tiver dados.
        """
        data = await self.fetch_paginated(self.ENDPOINT)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT)
