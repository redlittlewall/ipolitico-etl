"""Rotas filhas de /partidos/{id}/<suffix>."""

from __future__ import annotations

import logging
from typing import Any, Optional

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.base import SOURCE_PAGE_COL
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class PartidoChildRouteExtractor(CamaraBaseExtractor):
    """Extrator base para rotas filhas de /partidos/{id}/<suffix>.

    Percorre a lista de IDs de partidos e coleta os dados da rota filha
    para cada um, adicionando colunas de auditoria (``id_partido`` e
    ``_source_url`` com parâmetros opcionais de data/legislatura).
    """

    route_suffix: str = ""

    async def extract(
        self,
        partido_ids: list[int] | None = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        legislatura_id: Optional[int] = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai dados da rota filha para cada partido informado.

        Args:
            partido_ids: Lista de IDs dos partidos a consultar.
            start_date: Data inicial de filtro (YYYY-MM-DD), opcional.
            end_date: Data final de filtro (YYYY-MM-DD), opcional.
            legislatura_id: ID da legislatura para filtro, opcional.

        Returns:
            pl.DataFrame: DataFrame com os dados brutos acrescidos de
                          ``id_partido`` e ``_source_url``, ou vazio.
        """
        if not partido_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        raw_params = {
            ApiParams.DATA_INICIO.value: start_date,
            ApiParams.DATA_FIM.value: end_date,
            ApiParams.ID_LEGISLATURA.value: legislatura_id,
        }
        common_params = self.build_params(raw_params)
        # Cópia limpa (sem itens/pagina) para montar as URLs de auditoria;
        # o fetch_paginated muta common_params injetando itens/pagina.
        audit_params = dict(common_params)

        for pid in partido_ids:
            endpoint = f"{ApiRoutes.PARTIDOS.value}/{pid}/{self.route_suffix}"
            try:
                data = await self.fetch_paginated(endpoint, common_params)
                for item in data:
                    if isinstance(item, dict):
                        # URL replayável até o registro: inclui a página exata
                        # de origem e não vaza a chave interna _source_page.
                        page = item.pop(SOURCE_PAGE_COL, None)
                        row_url = self.build_list_source_url(endpoint, audit_params, page)
                        rows.append(
                            {
                                **item,
                                "id_partido": int(pid),
                                "_source_url": row_url,
                            }
                        )
            except Exception as e:
                logger.warning("Erro em %s do partido %s: %s", self.route_suffix, pid, e)

        if not rows:
            return pl.DataFrame()
        df = pl.DataFrame(rows, infer_schema_length=None)
        return df.select(["_source_url"] + [c for c in df.columns if c != "_source_url"])


class PartidoMembrosExtractor(PartidoChildRouteExtractor):
    """Rota /partidos/{id}/membros."""

    route_suffix = "membros"


class PartidoLideresExtractor(PartidoChildRouteExtractor):
    """Rota /partidos/{id}/lideres."""

    route_suffix = "lideres"
