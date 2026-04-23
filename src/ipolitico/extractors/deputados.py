import logging
import sqlite3

import polars as pl

from ipolitico.core.config import LEGISLATURA_ATUAL
from ipolitico.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


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

    async def extract(
        self, data_inicio: str = None, data_fim: str = None, legislatura: int = LEGISLATURA_ATUAL
    ) -> pl.DataFrame:
        """
        Extrai a lista de deputados da legislatura atual.
        Neste caso, optamos por um Full Load (Carga Total) por ser um volume pequeno.
        """
        params = {"ordem": "ASC", "ordenarPor": "nome"}

        if data_inicio:
            params["dataInicio"] = data_inicio
        if data_fim:
            params["dataFim"] = data_fim
        if legislatura:
            params["idLegislatura"] = legislatura

        logger.info("Extraindo lista básica de deputados...")

        dados = await self.client.fetch("deputados", params=params)
        return pl.DataFrame(dados)

    async def extract_detalhes(self, deputados_ids: list) -> pl.DataFrame:
        """
        Busca informações profundas (CPF, nascimento, escolaridade) de uma lista de IDs.
        Tira máximo proveito do motor de concorrência.
        """
        logger.info(f"Buscando detalhes profundos de {len(deputados_ids)} deputados...")

        async def fetch_detalhe(deputado_id: int) -> pl.DataFrame:
            endpoint = f"deputados/{deputado_id}"
            try:
                resp = await self.client.fetch(endpoint)
                if resp and isinstance(resp, dict):
                    return pl.DataFrame([resp])
                return pl.DataFrame()
            except Exception as e:
                logger.debug(f"Falha ao buscar detalhes do deputado {deputado_id}: {e}")
                return pl.DataFrame()

        # Motor concorrente com 10 requisições simultâneas
        df_detalhes = await self.execute_concurrently(deputados_ids, fetch_detalhe, max_workers=10)

        if not df_detalhes.is_empty():
            logger.info("Detalhes extraídos com sucesso.")

        return df_detalhes
