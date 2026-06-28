import logging
from typing import Any, Optional

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class ProposicoesExtractor(CamaraBaseExtractor):
    """
    Extrator responsável pelo domínio de Proposições Legislativas na API.

    Busca Projetos de Lei, PECs e Requerimentos de forma crua.
    A orquestração de chamadas particionadas por ano fica a cargo do PipelineRunner.
    """

    async def extract(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        year: Optional[int] = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Executa a extração bruta de proposições da Câmara.

        Args:
            start_date (str, optional): Data de início (YYYY-MM-DD).
            end_date (str, optional): Data de fim (YYYY-MM-DD).
            year (int, optional): Ano específico da proposição.
            **kwargs: Parâmetros extras.

        Returns:
            pl.DataFrame: DataFrame contendo os dados brutos de proposições.
        """
        raw_params = {
            ApiParams.ANO: year,
            ApiParams.DATA_INICIO.value: start_date,
            ApiParams.DATA_FIM.value: end_date,
            ApiParams.ORDEM: ApiParams.ORDEM_ASC.value,
            ApiParams.ORDENAR_POR: ApiParams.ID.value,
        }

        logger.debug(f"Fetching proposicoes with params: {raw_params}")
        data = await self.fetch_paginated(
            ApiRoutes.PROPOSICOES.value, self.build_params(raw_params)
        )

        return pl.DataFrame(data) if data else pl.DataFrame()
