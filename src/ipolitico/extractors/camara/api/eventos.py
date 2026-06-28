import logging
from typing import Any, Optional

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class EventosExtractor(CamaraBaseExtractor):
    """Eventos de órgãos da Câmara (GET /eventos)."""

    async def extract(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        raw_params = {
            ApiParams.DATA_INICIO.value: start_date,
            ApiParams.DATA_FIM.value: end_date,
            ApiParams.ORDEM.value: ApiParams.ORDEM_ASC.value,
            ApiParams.ORDENAR_POR.value: "dataHoraInicio",
        }
        data = await self.fetch_paginated(ApiRoutes.EVENTOS.value, self.build_params(raw_params))
        return pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
