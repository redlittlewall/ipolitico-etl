"""Rotas filhas de /frentes/{id}/membros."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class FrenteMembrosExtractor(CamaraBaseExtractor):
    async def extract(self, frente_ids: list[int] | None = None, **kwargs: Any) -> pl.DataFrame:
        if not frente_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        for fid in frente_ids:
            endpoint = f"{ApiRoutes.FRENTES.value}/{fid}/membros"
            try:
                data = await self.fetch_unpaginated(endpoint, {})
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, "id_frente": int(fid)})
            except Exception as e:
                logger.error("Erro em membros da frente %s: %s", fid, e)

        return pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()
