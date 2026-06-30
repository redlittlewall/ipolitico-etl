import logging
from typing import Any, Dict, List

from ipolitico.core.camara_client import CamaraClient
from ipolitico.core.config import CAMARA_PAGE_SIZE
from ipolitico.core.constants import ApiParams
from ipolitico.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class CamaraBaseExtractor(BaseExtractor):
    """
    Extrator Base específico para a API de Dados Abertos da Câmara.

    Atua como uma ponte (Adapter) entre o motor assíncrono genérico e as
    particularidades da API da Câmara, gerenciando a injeção automática de
    parâmetros de paginação e a normalização de Enumerações, sem deter
    estado ou regras de negócio.
    """

    def __init__(self, client: CamaraClient):
        """
        Inicializa o extrator base da API.

        Args:
            client (CamaraClient): Cliente HTTP configurado para requisições na Câmara.
        """
        self.client = client

    def build_params(self, raw_params: Dict[Any, Any]) -> Dict[str, Any]:
        """
        Limpa parâmetros nulos e resolve Enums para strings compreensíveis pela API.

        Args:
            raw_params (Dict[Any, Any]): Dicionário de parâmetros de requisição cru.

        Returns:
            Dict[str, Any]: Dicionário purificado e pronto para serialização na URL.
        """
        cleaned_params = {}
        for key, value in raw_params.items():
            if value is not None:
                param_key = key.value if isinstance(key, ApiParams) else key
                cleaned_params[param_key] = value
        return cleaned_params

    async def fetch_paginated(self, endpoint: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Lida com a paginação infinita da API da Câmara.

        Percorre as páginas da API automaticamente até que uma lista vazia
        ou uma página com menos itens que o limite máximo seja retornada.

        Args:
            endpoint (str): Caminho relativo do recurso (ex: 'deputados/1/despesas').
            params (Dict[str, Any]): Parâmetros de filtro e ordenação já limpos.

        Returns:
            List[Dict[str, Any]]: Todos os registros acumulados das múltiplas páginas.
        """
        page_limit_key = ApiParams.ITENS.value
        if params.get(page_limit_key) is None:
            params[page_limit_key] = CAMARA_PAGE_SIZE
        page_limit = int(params[page_limit_key])

        all_data = []
        page = 1

        while True:
            params[ApiParams.PAGINA.value] = page

            data = await self.client.fetch(endpoint, params=params)

            if not data:
                break

            all_data.extend(data)

            if len(data) < page_limit:
                break

            page += 1

        return all_data

    async def fetch_unpaginated(
        self, endpoint: str, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Obtém dados de um endpoint que NÃO suporta paginação (itens/pagina).

        Alguns endpoints da API Câmara (ex: /proposicoes/{id}/tramitacoes,
        /eventos/{id}/deputados) rejeitam os parâmetros 'itens' e 'pagina'
        com erro 400/405. Para estes, use este método em vez de fetch_paginated.

        Args:
            endpoint (str): Caminho relativo do recurso.
            params (Dict[str, Any]): Parâmetros de filtro (ex: dataInicio, dataFim).

        Returns:
            List[Dict[str, Any]]: Registros retornados pela API.
        """
        return await self.client.fetch(endpoint, params=params)

    async def probe_endpoint(self, endpoint: str) -> int:
        """
        Sonda o endpoint pedindo apenas 1 item para validar a existência de dados.
        Evita chamadas em massa desnecessárias para recursos vazios.

        Args:
            endpoint (str): Caminho relativo do recurso.

        Returns:
            int: Quantidade de itens retornados (0 se vazio).
        """
        try:
            data = await self.client.fetch(endpoint, params={"itens": 1})
            return len(data) if data else 0
        except Exception as e:
            logger.error(f"Erro ao sondar o endpoint {endpoint}: {e}")
            return 0
