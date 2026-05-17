"""Rotas filhas de /orgaos/{id}/<suffix>."""

from __future__ import annotations

import logging
from typing import Any, Optional

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class OrgaoChildRouteExtractor(CamaraBaseExtractor):
    route_suffix: str = ""

    async def extract(
        self,
        orgao_ids: list[int] | None = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        if not orgao_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        raw_params = {
            ApiParams.DATA_INICIO.value: start_date,
            ApiParams.DATA_FIM.value: end_date,
        }
        params = self.build_params(raw_params)

        for oid in orgao_ids:
            endpoint = f"{ApiRoutes.ORGAOS.value}/{oid}/{self.route_suffix}"
            try:
                data = await self.fetch_paginated(endpoint, params)
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, "id_orgao": int(oid)})
            except Exception as e:
                logger.error("Erro em %s do órgão %s: %s", self.route_suffix, oid, e)

        return pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()


class OrgaoMembrosExtractor(OrgaoChildRouteExtractor):
    route_suffix = "membros"


class OrgaoEventosExtractor(OrgaoChildRouteExtractor):
    route_suffix = "eventos"


class OrgaoVotacoesExtractor(OrgaoChildRouteExtractor):
    route_suffix = "votacoes"
