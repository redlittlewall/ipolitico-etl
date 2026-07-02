import logging
from typing import Any, Optional

import polars as pl

from ipolitico.core.constants import ApiParams, ApiRoutes
from ipolitico.extractors.camara.api.camara_base import CamaraBaseExtractor

logger = logging.getLogger(__name__)


class DeputadosExtractor(CamaraBaseExtractor):
    """
    Extrator responsável pelo domínio de Deputados Federais na API.

    Atua de forma estrita em I/O, extraindo dados cadastrais e detalhes
    individuais sem deter estado ou gerenciar filas de execução.
    """

    source_url_format: str = "https://dadosabertos.camara.leg.br/api/v2/deputados/{resource_id}"

    async def extract(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        legislatura_id: Optional[int] = None,
        **kwargs: Any,
    ) -> pl.DataFrame:
        """
        Extrai a lista de deputados com base nos filtros fornecidos.

        Args:
            start_date (str, optional): Data inicial de filtro (YYYY-MM-DD).
            end_date (str, optional): Data final de filtro (YYYY-MM-DD).
            legislatura_id (int, optional): ID numérico da legislatura.
            **kwargs: Parâmetros adicionais.

        Returns:
            pl.DataFrame: DataFrame contendo os dados brutos da lista de deputados
                          com coluna ``_source_url`` de auditoria.
        """
        raw_params = {
            ApiParams.DATA_INICIO.value: start_date,
            ApiParams.DATA_FIM.value: end_date,
            ApiParams.ID_LEGISLATURA.value: legislatura_id,
        }

        logger.debug(f"Fetching deputados from API with params: {raw_params}")
        data = await self.fetch_paginated(ApiRoutes.DEPUTADOS.value, self.build_params(raw_params))

        df = pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
        return self._inject_source_url(df, "deputados", resource_id_col="id")

    async def extract_detalhes(self, deputado_id: int) -> pl.DataFrame:
        """
        Extrai informações detalhadas de um único deputado.

        Args:
            deputado_id (int): O ID único do parlamentar.

        Returns:
            pl.DataFrame: Um DataFrame (de 1 linha) com o detalhe bruto,
                          incluindo os dicionários/listas originais da API.
        """
        endpoint = f"{ApiRoutes.DEPUTADOS.value}/{deputado_id}"
        resp = await self.client.fetch(endpoint)

        return pl.DataFrame([resp]) if resp else pl.DataFrame()

    async def extract_child_route(self, deputado_id: int, route_suffix: str) -> pl.DataFrame:
        """
        Extrai rotas biográficas secundárias estáticas (ex: profissoes, ocupacoes).

        Args:
            deputado_id (int): O ID único do parlamentar.
            route_suffix (str): O sufixo da rota (ex: 'profissoes').

        Returns:
            pl.DataFrame: Os dados brutos retornados pela rota.
        """
        endpoint = f"{ApiRoutes.DEPUTADOS.value}/{deputado_id}/{route_suffix}"
        data = await self.client.fetch(endpoint)

        return pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()

    async def extract_temporal_route(
        self, deputado_id: int, route_suffix: str, start_date: str, end_date: str
    ) -> pl.DataFrame:
        """
        Extrai rotas paginadas que dependem de janelas temporais (ex: discursos, orgaos).

        Args:
            deputado_id (int): O ID único do parlamentar.
            route_suffix (str): O sufixo da rota (ex: 'discursos').
            start_date (str): Data inicial (YYYY-MM-DD).
            end_date (str): Data final (YYYY-MM-DD).

        Returns:
            pl.DataFrame: Todos os registros brutos coletados nas páginas.
        """
        endpoint = f"{ApiRoutes.DEPUTADOS.value}/{deputado_id}/{route_suffix}"
        raw_params = {
            ApiParams.DATA_INICIO.value: start_date,
            ApiParams.DATA_FIM.value: end_date,
        }

        data = await self.fetch_paginated(endpoint, self.build_params(raw_params))
        return pl.DataFrame(data, infer_schema_length=None) if data else pl.DataFrame()
