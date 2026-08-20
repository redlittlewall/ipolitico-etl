"""Extrator do domínio cg_emendas — emendas parlamentares por ano (API v3).

Fonte real do ticket 04: API v3 ``/api-de-dados/emendas`` com o filtro ``ano``
("respeita a janela da API por ano" do ticket; contrato confirmado na validação
real — o filtro ``ano`` recorta a coleção e o walk continua com ``pagina``). Sem
rota bulk: o dump ``/download-de-dados/emendas-parlamentares`` é um único ZIP
que re-publica o histórico inteiro a cada geração — conflita com append-only.

O job anual chega pelo mapper da ``AnnualWindowStrategy`` como ``{"ano": y}`` →
``extract(ano=...)``. Sem ``ano``, a coleção inteira é varrida (walk livre) —
também válido na API.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from ipolitico.extractors.portal_transparencia.api.base_extractor import (
    PortalTransparenciaBaseExtractor,
)


class PortalEmendasApiExtractor(PortalTransparenciaBaseExtractor):
    """
    Extrator das emendas parlamentares (API v3, por ano).

    Página o recurso ``api-de-dados/emendas`` até esgotar, aplicando o filtro
    ``ano`` quando informado (janela anual) e injeta ``_source_url`` por página
    (``...?ano=YYYY&pagina=N``) para auditoria replayável. Devolve o raw como
    veio da API (``codigoEmenda``, ``ano``, ``autor``, ``valor*`` como strings
    vírgula-decimal — a tipagem/moeda vive no transformer), sem regras de negócio.
    """

    ENDPOINT = "api-de-dados/emendas"

    async def extract(self, ano: int | None = None, **kwargs: Any) -> pl.DataFrame:
        """
        Extrai as emendas parlamentares do ano (ou a coleção inteira).

        Args:
            ano: Ano de referência (opcional). Quando ausente, a coleção inteira
                é varrida (walk livre — a API aceita ``pagina`` sozinho).
            **kwargs: Argumentos adicionais (ignorados).

        Returns:
            DataFrame bruto com as colunas do DTO de emendas e ``_source_url``
            por linha apontando para a página de origem (com ``ano`` no query
            string quando filtrado). DataFrame vazio se a API não tiver dados.
        """
        params = {"ano": ano} if ano else None
        data = await self.fetch_paginated(self.ENDPOINT, params=params)
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, self.ENDPOINT, params=params)
