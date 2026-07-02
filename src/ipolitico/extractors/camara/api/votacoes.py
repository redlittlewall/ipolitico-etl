import logging
from typing import Any, Optional

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class VotacoesExtractor(CamaraBaseExtractor):
    """
    Extrator responsável pelo domínio de Votações e Votos Nominais na API.

    Remove qualquer manipulação estrutural de JSONs aninhados, fornecendo
    a resposta HTTP exata no formato de DataFrame.
    """

    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/votacoes/{resource_id}"

    async def extract(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None, **kwargs: Any
    ) -> pl.DataFrame:
        """
        Extrai o cabeçalho e os metadados brutos das votações.

        Args:
            start_date (str, optional): Data inicial (YYYY-MM-DD).
            end_date (str, optional): Data final (YYYY-MM-DD).
            **kwargs: Parâmetros adicionais.

        Returns:
            pl.DataFrame: Metadados puros das votações com coluna ``_source_url``
                          de auditoria.
        """
        raw_params = {
            ApiParams.DATA_INICIO.value: start_date,
            ApiParams.DATA_FIM.value: end_date,
            ApiParams.ORDEM.value: ApiParams.ORDEM_ASC.value,
            ApiParams.ORDENAR_POR.value: "data",
        }

        logger.debug(f"Fetching votacoes from {start_date} to {end_date}")
        data = await self.fetch_paginated(ApiRoutes.VOTACOES.value, self.build_params(raw_params))

        if not data:
            logger.info(
                "Nenhuma votação retornada pela API para o período %s a %s.",
                start_date,
                end_date,
            )
            return pl.DataFrame()

        logger.info("API votações: %s registros brutos no período.", len(data))
        df = pl.DataFrame(data, infer_schema_length=None)
        return self._inject_source_url(df, "votacoes", resource_id_col="id")

    async def extract_votos(self, votacao_id: str) -> pl.DataFrame:
        """
        Extrai a lista de votos nominais de uma votação específica.

        Args:
            votacao_id (str): O ID único da votação.

        Returns:
            pl.DataFrame: Dados brutos, preservando nós complexos como dicionários internos.
        """
        endpoint = f"{ApiRoutes.VOTACOES.value}/{votacao_id}/{ApiRoutes.VOTOS.value}"

        logger.debug(f"Fetching votos for votacao_id: {votacao_id}")
        data = await self.client.fetch(endpoint)

        return pl.DataFrame(data) if data else pl.DataFrame()
