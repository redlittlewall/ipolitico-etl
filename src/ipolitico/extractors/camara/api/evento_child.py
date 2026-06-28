"""Rotas filhas de /eventos/{id}/<suffix>."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class EventoChildRouteExtractor(CamaraBaseExtractor):
    route_suffix: str = ""
    parent_id_field: str = "id_evento"

    async def extract(self, evento_ids: list[int] | None = None, **kwargs: Any) -> pl.DataFrame:
        if not evento_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        for eid in evento_ids:
            endpoint = f"{ApiRoutes.EVENTOS.value}/{eid}/{self.route_suffix}"
            try:
                data = await self.fetch_unpaginated(endpoint, {})
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, self.parent_id_field: int(eid)})
            except Exception as e:
                logger.warning("Erro em %s para evento %s: %s", self.route_suffix, eid, e)

        return pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()


class EventoDeputadosExtractor(EventoChildRouteExtractor):
    route_suffix = "deputados"


class EventoVotacoesExtractor(EventoChildRouteExtractor):
    route_suffix = "votacoes"


class EventoPautaExtractor(EventoChildRouteExtractor):
    route_suffix = "pauta"


class EventoOrgaosExtractor(EventoChildRouteExtractor):
    route_suffix = "orgaos"
