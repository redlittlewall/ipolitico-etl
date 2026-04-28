from typing import Any

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import CAMARA_PAGE_SIZE
from ipolitico.core.constants import ApiParams
from ipolitico.extractors.base import BaseExtractor, IStateStore


class CamaraBaseExtractor(BaseExtractor):
    """
    Extrator Base específico para a API de Dados Abertos da Câmara.

    Atua como uma ponte (Adapter) entre o motor assíncrono genérico e as
    regras de negócio estatais, gerenciando a injeção automática de parâmetros
    de paginação e a normalização de Enumerações.
    """

    def __init__(self, client: CamaraClient, state_store: IStateStore):
        super().__init__(state_store)
        self.client = client

    def build_params(self, raw_params: dict[Any, Any]) -> dict[str, Any]:
        """
        Limpa parâmetros nulos e resolve Enums para strings compreensíveis pela API.

        Args:
            raw_params (dict): Dicionário de parâmetros de requisição cru.

        Returns:
            dict: Dicionário purificado e pronto para serialização na URL.
        """
        cleaned_params = {}
        for key, value in raw_params.items():
            if value is not None:
                param_key = key.value if isinstance(key, ApiParams) else key
                cleaned_params[param_key] = value
        return cleaned_params

    async def fetch_paginated(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Lida com a paginação infinita da Câmara (baseada em 'pagina' e 'itens').

        Percorre as páginas da API automaticamente até que uma lista vazia
        ou uma página com menos itens que o limite máximo (CAMARA_PAGE_SIZE) seja retornada.

        Args:
            endpoint (str): Caminho relativo do recurso (ex: 'deputados/1/despesas').
            params (dict): Parâmetros de filtro e ordenação já limpos.

        Returns:
            list: Todos os registros acumulados das múltiplas páginas.
        """
        all_data = []
        pagina = 1

        while True:
            params[ApiParams.PAGINA.value] = pagina

            dados = await self.client.fetch(endpoint, params=params)

            if not dados:
                break

            all_data.extend(dados)

            if len(dados) < CAMARA_PAGE_SIZE:
                break

            pagina += 1

        return all_data
