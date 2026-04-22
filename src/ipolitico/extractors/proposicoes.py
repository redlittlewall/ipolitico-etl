import polars as pl

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import LEGISLATURA_ATUAL


class ProposicoesExtractor:
    """
    Extrator responsável por buscar metadados de propostas legislativas.
    Focado em transparência de tramitação, evitando contagens de volume simples.
    """

    def __init__(self, client: CamaraClient):
        self.client = client

    async def extract_atuais(self) -> pl.DataFrame:
        """
        Extrai proposições da legislatura atual.
        """
        endpoint = "proposicoes"
        # Buscamos as mais recentes primeiro para garantir dados novos no banco
        params = {"idLegislatura": LEGISLATURA_ATUAL, "ordem": "DESC", "ordenarPor": "id"}

        # O cliente já gerencia retentativas e erros da API
        dados_brutos = await self.client.fetch(endpoint, params=params)

        return pl.DataFrame(dados_brutos)
