"""Rotas filhas de /proposicoes/{id}/<suffix> (tramitações, autores)."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class ProposicaoChildRouteExtractor(CamaraBaseExtractor):
    route_suffix: str = ""

    async def extract(self, proposicao_ids: list[int] | None = None, **kwargs: Any) -> pl.DataFrame:
        if not proposicao_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        for pid in proposicao_ids:
            endpoint = f"{ApiRoutes.PROPOSICOES.value}/{pid}/{self.route_suffix}"
            try:
                data = await self.fetch_unpaginated(endpoint, {})
                if not data:
                    continue
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, "id_proposicao": int(pid)})
            except Exception as e:
                logger.warning("Erro em %s para proposição %s: %s", self.route_suffix, pid, e)

        return pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()


class TramitacoesExtractor(ProposicaoChildRouteExtractor):
    route_suffix = "tramitacoes"


class AutoresExtractor(ProposicaoChildRouteExtractor):
    route_suffix = "autores"


class RelacionadasExtractor(ProposicaoChildRouteExtractor):
    route_suffix = "relacionadas"


class TemasExtractor(ProposicaoChildRouteExtractor):
    route_suffix = "temas"


class ProposicoesVotacoesExtractor(ProposicaoChildRouteExtractor):
    route_suffix = "votacoes"
