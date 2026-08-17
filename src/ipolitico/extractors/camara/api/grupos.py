from typing import Any, Optional

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor


class GruposExtractor(CamaraBaseExtractor):
    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/grupos/{resource_id}"

    async def extract(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None, **kwargs: Any
    ):
        """
        Extrai lista de grupos parlamentares da API.

        Args:
            start_date: Ignorado.
            end_date: Ignorado.
            **kwargs: Parâmetros adicionais.

        Returns:
            pl.DataFrame: Dados brutos com ``_source_url`` de auditoria.
        """
        _ = start_date, end_date
        raw_params = {
            ApiParams.ORDEM.value: ApiParams.ORDEM_ASC.value,
            ApiParams.ORDENAR_POR.value: ApiParams.ID.value,
        }
        data = await self.fetch_paginated(ApiRoutes.GRUPOS.value, self.build_params(raw_params))
        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, "grupos", resource_id_col="id")
