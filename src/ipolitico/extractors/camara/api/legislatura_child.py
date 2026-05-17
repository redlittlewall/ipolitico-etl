"""Rotas filhas de /legislaturas/{id}/<suffix>."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class LegislaturaChildRouteExtractor(CamaraBaseExtractor):
    route_suffix: str = ""

    async def extract(
        self, legislatura_ids: list[int] | None = None, **kwargs: Any
    ) -> pl.DataFrame:
        if not legislatura_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        for lid in legislatura_ids:
            endpoint = f"{ApiRoutes.LEGISLATURAS.value}/{lid}/{self.route_suffix}"
            try:
                data = await self.fetch_paginated(endpoint, {})
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, "id_legislatura": int(lid)})
            except Exception as e:
                logger.error("Erro em %s da legislatura %s: %s", self.route_suffix, lid, e)

        return pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()


class LegislaturaLideresExtractor(LegislaturaChildRouteExtractor):
    route_suffix = "lideres"


class LegislaturaMesaExtractor(LegislaturaChildRouteExtractor):
    route_suffix = "mesa"
