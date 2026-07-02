"""Rotas filhas de /orgaos/{id}/<suffix>."""

from __future__ import annotations

import logging
from typing import Any, Optional

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class OrgaoChildRouteExtractor(CamaraBaseExtractor):
    """Extrator base para rotas filhas de /orgaos/{id}/<suffix>.

    Percorre a lista de IDs de órgãos fornecida e coleta os dados
    da rota filha para cada um, adicionando colunas de auditoria
    (``id_orgao`` e ``_source_url`` com os parâmetros opcionais de data).
    """

    route_suffix: str = ""

    async def extract(
        self,
        orgao_ids: list[int] | None = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """Extrai dados da rota filha para cada órgão informado.

        Args:
            orgao_ids: Lista de IDs dos órgãos a consultar.
            start_date: Data inicial de filtro (YYYY-MM-DD), opcional.
            end_date: Data final de filtro (YYYY-MM-DD), opcional.

        Returns:
            pl.DataFrame: DataFrame com os dados brutos acrescidos de
                          ``id_orgao`` e ``_source_url``, ou vazio.
        """
        if not orgao_ids:
            return pl.DataFrame()

        rows: list[dict] = []
        raw_params = {
            ApiParams.DATA_INICIO.value: start_date,
            ApiParams.DATA_FIM.value: end_date,
        }
        common_params = self.build_params(raw_params)

        for oid in orgao_ids:
            endpoint = f"{ApiRoutes.ORGAOS.value}/{oid}/{self.route_suffix}"
            url = self.build_source_url(endpoint, params=common_params)
            try:
                data = await self.fetch_unpaginated(endpoint, common_params)
                for item in data:
                    if isinstance(item, dict):
                        rows.append({**item, "id_orgao": int(oid), "_source_url": url})
            except Exception as e:
                logger.warning("Erro em %s do órgão %s: %s", self.route_suffix, oid, e)

        if not rows:
            return pl.DataFrame()
        df = pl.DataFrame(rows, infer_schema_length=None)
        return df.select(["_source_url"] + [c for c in df.columns if c != "_source_url"])


class OrgaoMembrosExtractor(OrgaoChildRouteExtractor):
    """Rota /orgaos/{id}/membros."""

    route_suffix = "membros"


class OrgaoEventosExtractor(OrgaoChildRouteExtractor):
    """Rota /orgaos/{id}/eventos."""

    route_suffix = "eventos"


class OrgaoVotacoesExtractor(OrgaoChildRouteExtractor):
    """Rota /orgaos/{id}/votacoes."""

    route_suffix = "votacoes"
