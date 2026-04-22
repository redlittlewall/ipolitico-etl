import polars as pl

from ipolitico.core.config import LEGISLATURA_ATUAL
from ipolitico.extractors.base import BaseExtractor


class DeputadosExtractor(BaseExtractor):
    """
    Extrator responsável por buscar a listagem de deputados federais.
    Consome a rota /deputados da API da Câmara.
    """

    async def extract(self) -> pl.DataFrame:
        """
        Extrai a lista de deputados da legislatura atual.
        Neste caso, optamos por um Full Load (Carga Total) por ser um volume pequeno.
        """
        params = {"idLegislatura": LEGISLATURA_ATUAL, "ordem": "ASC", "ordenarPor": "nome"}

        dados = await self.client.fetch("deputados", params=params)
        return pl.DataFrame(dados)
