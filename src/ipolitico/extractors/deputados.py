import polars as pl
from ipolitico.core.client import CamaraClient


class DeputadosExtractor:
    """
    Extrator responsável por buscar a listagem de deputados federais.
    Consome a rota /deputados da API da Câmara.
    """

    def __init__(self, client: CamaraClient):
        self.client = client

    async def extract_atuaies(self) -> pl.DataFrame:
        """
        Extrai os deputados da legislatura atual (57).
        """
        # Parâmetros conforme documentação da API para a 57ª legislatura
        params = {"idLegislatura": 57, "ordem": "ASC", "ordenarPor": "nome"}

        # O fetch já trata throttling e erros silenciosos internamente
        dados_brutos = await self.client.fetch("deputados", params=params)

        # Converte para DataFrame do Polars para processamento eficiente
        return pl.DataFrame(dados_brutos)
