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
        """
        Extrai detalhes de entidades por ID.

        Args:
            entity_ids: Lista de IDs para buscar.
            **kwargs: Parâmetros adicionais.

        Returns:
            pl.DataFrame: Dados brutos com coluna ``_source_url`` de auditoria.
        """
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
                logger.warning("Erro em detalhe %s/%s: %s", self.base_route, eid, e)

        df = pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()
        return self._inject_source_url(df, self.base_route, resource_id_col="id")


class DeputadosDetalheExtractor(DetailByIdExtractor):
    base_route = "deputados"
    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/deputados/{resource_id}"


class OrgaosDetalheExtractor(DetailByIdExtractor):
    base_route = "orgaos"
    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/orgaos/{resource_id}"


class EventosDetalheExtractor(DetailByIdExtractor):
    base_route = "eventos"
    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/eventos/{resource_id}"


class VotacoesDetalheExtractor(DetailByIdExtractor):
    base_route = "votacoes"
    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/votacoes/{resource_id}"


class FrentesDetalheExtractor(DetailByIdExtractor):
    base_route = "frentes"
    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/frentes/{resource_id}"


class PartidosDetalheExtractor(DetailByIdExtractor):
    base_route = "partidos"
    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/partidos/{resource_id}"


class GruposDetalheExtractor(DetailByIdExtractor):
    base_route = "grupos"
    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/grupos/{resource_id}"


class LegislaturasDetalheExtractor(DetailByIdExtractor):
    base_route = "legislaturas"
    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/legislaturas/{resource_id}"


class BlocosDetalheExtractor(DetailByIdExtractor):
    """Extrator para o endpoint GET /blocos/{id} (detalhe de bloco parlamentar)."""

    base_route = "blocos"
    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/blocos/{resource_id}"


class ProposicoesDetalheExtractor(DetailByIdExtractor):
    """Extrator para o endpoint GET /proposicoes/{id} (detalhe de proposição legislativa)."""

    base_route = "proposicoes"
    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/proposicoes/{resource_id}"
