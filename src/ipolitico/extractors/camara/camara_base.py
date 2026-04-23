from ipolitico.core.client import CamaraClient
from ipolitico.core.config import CAMARA_PAGE_SIZE
from ipolitico.core.constants import ApiParams
from ipolitico.extractors.base import BaseExtractor, IStateStore


class CamaraBaseExtractor(BaseExtractor):
    """
    Base específica para a API de Dados Abertos da Câmara.
    Sabe lidar com as rotas, cliente HTTP e a paginação peculiar deles.
    """

    def __init__(self, client: CamaraClient, state_store: IStateStore):
        super().__init__(state_store)
        self.client = client

    def build_params(self, raw_params: dict) -> dict:
        cleaned_params = {}
        for key, value in raw_params.items():
            if value is not None:
                param_key = key.value if isinstance(key, ApiParams) else key
                cleaned_params[param_key] = value
        return cleaned_params

    async def fetch_paginated(self, endpoint: str, params: dict) -> list:
        """Lida com a paginação específica da Câmara (pagina e itens)."""
        all_data = []
        pagina = 1
        params[ApiParams.ITENS.value] = CAMARA_PAGE_SIZE

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
