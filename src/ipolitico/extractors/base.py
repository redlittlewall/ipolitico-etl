import asyncio
import sqlite3
from abc import ABC, abstractmethod
from asyncio.log import logger

import polars as pl
from pydantic import ValidationError

from ipolitico.core.client import CamaraClient


class BaseExtractor(ABC):
    def __init__(self, client: CamaraClient, db_path: str):
        self.client = client
        self.db_path = db_path

    def _get_last_watermark(self, table: str, column: str) -> str | None:
        """Busca o ponto mais recente (watermark) no banco de dados."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT max({column}) FROM {table}")
                result = cursor.fetchone()[0]
                return result.split("T")[0] if result else None
        except Exception:
            return None

    @abstractmethod
    async def extract(self, **kwargs) -> pl.DataFrame:
        """Método que as subclasses devem implementar."""
        pass

    async def fetch_paginated(self, endpoint: str, params: dict) -> list:
        """
        Pega todas as páginas de um endpoint automaticamente.
        """
        all_data = []
        pagina = 1
        params["itens"] = 100

        while True:
            params["pagina"] = pagina
            dados = await self.client.fetch(endpoint, params=params)

            if not dados:
                break

            all_data.extend(dados)

            # Se vieram menos de 100 itens, significa que é a última página
            if len(dados) < 100:
                break

            pagina += 1

        return all_data

    async def execute_concurrently(
        self, items: list, fetch_func, max_workers: int = 10
    ) -> pl.DataFrame:
        """
        Orquestrador central de concorrência.
        Recebe uma lista de IDs (ex: deputados), uma função de extração e roda tudo em paralelo.
        """
        semaforo = asyncio.Semaphore(max_workers)

        async def bounded_fetch(item):
            async with semaforo:
                return await fetch_func(item)

        tarefas = [bounded_fetch(item) for item in items]
        resultados = await asyncio.gather(*tarefas)

        frames = [r for r in resultados if isinstance(r, pl.DataFrame) and not r.is_empty()]
        return pl.concat(frames) if frames else pl.DataFrame()

    def validate_data(self, schema, data: list):
        """Valida a lista de dicionários contra um Schema Pydantic."""
        try:
            return [schema(**item).dict() for item in data]
        except ValidationError as e:
            logger.error(f"Erro de contrato na API: {e.json()}")
            raise
