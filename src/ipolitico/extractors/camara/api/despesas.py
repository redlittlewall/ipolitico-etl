import logging
from typing import Any, Optional

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class DespesasExtractor(CamaraBaseExtractor):
    """
    Extrator responsável por buscar Cotas Parlamentares (Despesas) na API.

    A delegação do fatiamento (chunking) e orquestração assíncrona pertence
    agora ao PipelineRunner. Esta classe lida exclusivamente com o fetch
    direto à API de acordo com os parâmetros enviados.
    """

    async def extract(
        self, deputado_id: int, year: int, month: Optional[int] = None, **kwargs: Any
    ) -> pl.DataFrame:
        """
        Busca todas as despesas de um deputado em um ano/mês específico.

        Args:
            deputado_id (int): O ID único do parlamentar.
            year (int): O ano de referência.
            month (int, optional): O mês de referência.
            **kwargs: Parâmetros adicionais (ignorado neste escopo básico).

        Returns:
            pl.DataFrame: DataFrame contendo as despesas estritamente brutos.
        """
        endpoint = f"{ApiRoutes.DEPUTADOS.value}/{deputado_id}/despesas"

        raw_params = {
            ApiParams.ANO: year,
            ApiParams.ORDEM: ApiParams.ORDEM_ASC.value,
            ApiParams.ORDENAR_POR: ApiParams.DATA_DOCUMENTO.value,
        }

        if month:
            raw_params[ApiParams.MES] = month

        logger.debug(f"Fetching despesas for dep {deputado_id} ({year}/{month})")
        data = await self.fetch_paginated(endpoint, self.build_params(raw_params))

        if not data:
            return pl.DataFrame()

        df = pl.DataFrame(data)

        if not df.is_empty():
            df = df.with_columns(pl.lit(deputado_id).alias(ApiParams.DEPUTADO_ID.value))

        return df
