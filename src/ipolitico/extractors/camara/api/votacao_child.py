"""Rotas filhas de /votacoes/{id}/<suffix> (orientações)."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class VotacaoChildRouteExtractor(CamaraBaseExtractor):
    route_suffix: str = ""

    async def extract(self, votacao_ids: list[Any] | None = None, **kwargs: Any) -> pl.DataFrame:
        if not votacao_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        for vid in votacao_ids:
            endpoint = f"{ApiRoutes.VOTACOES.value}/{vid}/{self.route_suffix}"
            try:
                data = await self.client.fetch(endpoint)
                if not data:
                    continue
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict):
                        rows.append({**item, "votacao_id": vid})
            except Exception as e:
                logger.warning("Erro em %s para votação %s: %s", self.route_suffix, vid, e)

        return pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()


class OrientacoesExtractor(VotacaoChildRouteExtractor):
    route_suffix = "orientacoes"
