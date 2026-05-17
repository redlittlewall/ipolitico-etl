from typing import Any, Optional

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor


class FrentesExtractor(CamaraBaseExtractor):
    async def extract(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        legislatura_id: Optional[int] = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        _ = start_date, end_date
        raw_params = {
            ApiParams.ID_LEGISLATURA.value: legislatura_id,
            ApiParams.ORDEM.value: ApiParams.ORDEM_ASC.value,
            ApiParams.ORDENAR_POR.value: ApiParams.ID.value,
        }
        data = await self.fetch_paginated(ApiRoutes.FRENTES.value, self.build_params(raw_params))
        return pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
