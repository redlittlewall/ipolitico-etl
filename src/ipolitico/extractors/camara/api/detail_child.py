"""GET /{entidade}/{id} — detalhe cadastral (campos além da listagem)."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class DetailByIdExtractor(CamaraBaseExtractor):
    base_route: str = ""
    id_kwarg: str = "entity_ids"

    async def extract(self, entity_ids: list[Any] | None = None, **kwargs: Any) -> pl.DataFrame:
        if not entity_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        for eid in entity_ids:
            endpoint = f"{self.base_route}/{eid}"
            try:
                data = await self.client.fetch(endpoint)
                if isinstance(data, dict):
                    rows.append(data)
            except Exception as e:
                logger.error("Erro em detalhe %s/%s: %s", self.base_route, eid, e)

        return pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()


class DeputadosDetalheExtractor(DetailByIdExtractor):
    base_route = "deputados"


class OrgaosDetalheExtractor(DetailByIdExtractor):
    base_route = "orgaos"


class EventosDetalheExtractor(DetailByIdExtractor):
    base_route = "eventos"


class VotacoesDetalheExtractor(DetailByIdExtractor):
    base_route = "votacoes"


class FrentesDetalheExtractor(DetailByIdExtractor):
    base_route = "frentes"


class PartidosDetalheExtractor(DetailByIdExtractor):
    base_route = "partidos"


class GruposDetalheExtractor(DetailByIdExtractor):
    base_route = "grupos"


class LegislaturasDetalheExtractor(DetailByIdExtractor):
    base_route = "legislaturas"
