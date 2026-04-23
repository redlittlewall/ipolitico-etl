import sqlite3

import polars as pl

from ipolitico.core.config import LEGISLATURA_ATUAL
from ipolitico.extractors.base import BaseExtractor


class DeputadosExtractor(BaseExtractor):
    """
    Extrator responsável por buscar a listagem de deputados federais.
    Consome a rota /deputados da API da Câmara.
    """

    async def get_all_ids(self) -> list[int]:
        """
        Retorna IDs do banco local; se vazio, extrai da API e salva primeiro.
        Isso retira a lógica de banco do main.py.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pl.read_database("SELECT id FROM deputados", conn)
                if not df.is_empty():
                    return df["id"].to_list()
        except Exception:
            pass

        df_new = await self.extract()
        # Nota: Idealmente, o Sink deveria ser usado aqui,
        # mas para manter simples, retornamos e o main salva.
        return df_new["id"].to_list()

    async def extract(self) -> pl.DataFrame:
        """
        Extrai a lista de deputados da legislatura atual.
        Neste caso, optamos por um Full Load (Carga Total) por ser um volume pequeno.
        """
        params = {"idLegislatura": LEGISLATURA_ATUAL, "ordem": "ASC", "ordenarPor": "nome"}

        dados = await self.client.fetch("deputados", params=params)
        return pl.DataFrame(dados)
