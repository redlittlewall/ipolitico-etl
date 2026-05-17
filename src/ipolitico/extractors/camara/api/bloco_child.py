"""Rotas filhas de /blocos/{id}/partidos."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class BlocoPartidosExtractor(CamaraBaseExtractor):
    async def extract(self, bloco_ids: list[int] | None = None, **kwargs: Any) -> pl.DataFrame:
        if not bloco_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        for bid in bloco_ids:
            endpoint = f"{ApiRoutes.BLOCOS.value}/{bid}/partidos"
            try:
                data = await self.fetch_paginated(endpoint, {})
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, "id_bloco": int(bid)})
            except Exception as e:
                logger.error("Erro em partidos do bloco %s: %s", bid, e)

        return pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()
