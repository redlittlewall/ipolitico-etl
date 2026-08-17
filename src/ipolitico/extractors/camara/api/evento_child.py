"""Rotas filhas de /eventos/{id}/<suffix>."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

from ipolitico.core.constants import ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class EventoChildRouteExtractor(CamaraBaseExtractor):
    """Extrator base para rotas filhas de /eventos/{id}/<suffix>.

    Percorre a lista de IDs de eventos e coleta os dados da rota filha
    para cada um, adicionando colunas de auditoria (``id_evento`` e
    ``_source_url``).
    """

    route_suffix: str = ""
    parent_id_field: str = "id_evento"

    async def extract(self, evento_ids: list[int] | None = None, **kwargs: Any) -> pl.DataFrame:
        """Extrai dados da rota filha para cada evento informado.

        Args:
            evento_ids: Lista de IDs dos eventos a consultar.

        Returns:
            pl.DataFrame: DataFrame com os dados brutos acrescidos de
                          ``id_evento`` e ``_source_url``, ou vazio.
        """
        if not evento_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        for eid in evento_ids:
            endpoint = f"{ApiRoutes.EVENTOS.value}/{eid}/{self.route_suffix}"
            url = self.build_source_url(endpoint)
            try:
                data = await self.fetch_unpaginated(endpoint, {})
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, self.parent_id_field: int(eid), "_source_url": url})
            except Exception as e:
                logger.warning("Erro em %s para evento %s: %s", self.route_suffix, eid, e)

        if not rows:
            return pl.DataFrame()
        df = pl.DataFrame(rows, infer_schema_length=None)
        return df.select(["_source_url"] + [c for c in df.columns if c != "_source_url"])


class EventoDeputadosExtractor(EventoChildRouteExtractor):
    """Rota /eventos/{id}/deputados."""

    route_suffix = "deputados"


class EventoVotacoesExtractor(EventoChildRouteExtractor):
    """Rota /eventos/{id}/votacoes."""

    route_suffix = "votacoes"


class EventoPautaExtractor(EventoChildRouteExtractor):
    """Rota /eventos/{id}/pauta."""

    route_suffix = "pauta"


class EventoOrgaosExtractor(EventoChildRouteExtractor):
    """Rota /eventos/{id}/orgaos."""

    route_suffix = "orgaos"
