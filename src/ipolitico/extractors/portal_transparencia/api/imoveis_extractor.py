"""Extrator do domínio cg_imoveis_funcionais — imóveis funcionais da União (API v3).

Correção de fonte do ticket 04: o dump bulk ``/download-de-dados/
imoveis-funcionais`` está INDISPONÍVEL (403 AccessDenied do S3) → fonte única é
a API v3 ``/api-de-dados/imoveis`` (walk livre com ``pagina`` — a API NÃO exige
filtro, contrato confirmado na validação real: ``id``, ``dataReferencia``,
``orgaoResponsavel``/``situacao``/``regiao`` como objetos aninhados, ``endereco``,
``cep``). Snapshot: 1 job sem parâmetros.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.extractors.portal_transparencia.api.base_extractor import (
    PortalTransparenciaBaseExtractor,
)


class PortalImoveisFuncionaisApiExtractor(PortalTransparenciaBaseExtractor):
    """
    Extrator do snapshot de imóveis funcionais da União (API v3).

    Página o recurso ``api-de-dados/imoveis`` até esgotar (walk livre, sem
    filtro obrigatório) e injeta ``_source_url`` por página (``...?pagina=N``)
    para auditoria replayável. Devolve o raw como veio da API (objetos aninhados
    ``orgaoResponsavel``/``situacao``/``regiao`` — o achatamento vive no
    transformer), sem aplicar regras de negócio.
    """

    ENDPOINT = "api-de-dados/imoveis"

    async def extract(self, **kwargs: Any) -> pl.DataFrame:
        """
        Extrai o snapshot de imóveis funcionais (lista paginada completa).

        Args:
            **kwargs: Argumentos adicionais (ignorados — snapshot sem janela).

        Returns:
            DataFrame bruto com ``id``, ``dataReferencia``, ``orgaoResponsavel``,
            ``situacao``, ``regiao``, ``endereco``, ``cep`` (structs aninhadas
            preservadas) e ``_source_url`` por linha apontando para a página de
            origem. DataFrame vazio se a API não tiver dados.
        """
        data = await self.fetch_paginated(self.ENDPOINT)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT)
