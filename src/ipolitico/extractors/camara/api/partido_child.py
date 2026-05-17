"""Rotas filhas de /partidos/{id}/<suffix>."""

from __future__ import annotations

import logging
from typing import Any, Optional

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class PartidoChildRouteExtractor(CamaraBaseExtractor):
    route_suffix: str = ""

    async def extract(
        self,
        partido_ids: list[int] | None = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        legislatura_id: Optional[int] = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        if not partido_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        raw_params = {
            ApiParams.DATA_INICIO.value: start_date,
            ApiParams.DATA_FIM.value: end_date,
            ApiParams.ID_LEGISLATURA.value: legislatura_id,
        }
        params = self.build_params(raw_params)

        for pid in partido_ids:
            endpoint = f"{ApiRoutes.PARTIDOS.value}/{pid}/{self.route_suffix}"
            try:
                data = await self.fetch_paginated(endpoint, params)
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, "id_partido": int(pid)})
            except Exception as e:
                logger.error("Erro em %s do partido %s: %s", self.route_suffix, pid, e)

        return pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()


class PartidoMembrosExtractor(PartidoChildRouteExtractor):
    route_suffix = "membros"


class PartidoLideresExtractor(PartidoChildRouteExtractor):
    route_suffix = "lideres"
