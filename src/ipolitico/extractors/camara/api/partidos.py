import logging
from typing import Any, Optional

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class PartidosExtractor(CamaraBaseExtractor):
    """Partidos com representação na Câmara (GET /partidos).

    Attributes:
        source_url_format: Template para URL do recurso específico na API.
    """

    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/partidos/{resource_id}"

    async def extract(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        legislatura_id: Optional[int] = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Extrai lista de partidos da API.

        Args:
            start_date: Data inicial (YYYY-MM-DD).
            end_date: Data final (YYYY-MM-DD).
            legislatura_id: ID da legislatura.
            **kwargs: Parâmetros adicionais.

        Returns:
            pl.DataFrame: Dados brutos com ``_source_url`` de auditoria.
        """
        raw_params = {
            ApiParams.DATA_INICIO.value: start_date,
            ApiParams.DATA_FIM.value: end_date,
            ApiParams.ID_LEGISLATURA.value: legislatura_id,
            ApiParams.ORDEM.value: ApiParams.ORDEM_ASC.value,
            ApiParams.ORDENAR_POR.value: "sigla",
        }
        data = await self.fetch_paginated(ApiRoutes.PARTIDOS.value, self.build_params(raw_params))
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, "partidos", resource_id_col="id")
