"""Rotas filhas de /grupos/{id}/<suffix>."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class GrupoChildRouteExtractor(CamaraBaseExtractor):
    route_suffix: str = ""

    async def extract(self, grupo_ids: list[int] | None = None, **kwargs: Any) -> pl.DataFrame:
        if not grupo_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        for gid in grupo_ids:
            endpoint = f"{ApiRoutes.GRUPOS.value}/{gid}/{self.route_suffix}"
            try:
                data = await self.fetch_unpaginated(endpoint, {})
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, "id_grupo": int(gid)})
            except Exception as e:
                logger.warning("Erro em %s do grupo %s: %s", self.route_suffix, gid, e)

        return pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()


class GrupoMembrosExtractor(GrupoChildRouteExtractor):
    route_suffix = "membros"


class GrupoHistoricoExtractor(GrupoChildRouteExtractor):
    route_suffix = "historico"
