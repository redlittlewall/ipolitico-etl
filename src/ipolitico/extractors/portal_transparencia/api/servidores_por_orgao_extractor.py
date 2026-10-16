"""Extrator do domínio cg_servidores — agregado de vínculos por órgão (API v3).

Correção de fonte do ticket 03: o roster completo ``/servidores`` exige filtro
de órgão (HTTP 400 sem ``codOrgao``) e a remuneração individual exige CPF por
servidor — inviável enumerar. A fonte real do snapshot é o agregado
``/api-de-dados/servidores/por-orgao`` (validado real no ticket 03): contagens
de pessoas/vínculos por (órgão, situação, tipo de vínculo, tipo de servidor,
licença), página a página, sem filtro adicional.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.extractors.portal_transparencia.api.base_extractor import (
    PortalTransparenciaBaseExtractor,
)


class PortalServidoresPorOrgaoApiExtractor(PortalTransparenciaBaseExtractor):
    """
    Extrator do agregado de servidores por órgão (API v3, snapshot).

    Página o recurso ``api-de-dados/servidores/por-orgao`` até esgotar e injeta
    ``_source_url`` por página (``...?pagina=N``) para auditoria replayável.
    Devolve o raw como veio da API (contagens Int, dimensões/órgãos String —
    a tipagem estrita vive no transformer), sem aplicar regras de negócio.
    """

    ENDPOINT = "api-de-dados/servidores/por-orgao"

    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """
        Extrai o agregado de vínculos por órgão (lista paginada completa).

        Args:
            **kwargs: Argumentos adicionais (ignorados — snapshot sem janela).

        Returns:
            DataFrame bruto com as 13 colunas do DTO ``por-orgao`` e
            ``_source_url`` por linha apontando para a página de origem.
            DataFrame vazio se a API não tiver dados.
        """
        data = await self.fetch_paginated(self.ENDPOINT)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT)
