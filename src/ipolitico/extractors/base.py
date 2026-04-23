import asyncio
from abc import ABC, abstractmethod
from typing import Protocol

import polars as pl

from ipolitico.core.client import CamaraClient
from ipolitico.core.config import CAMARA_PAGE_SIZE, MAX_CONCURRENT_REQUESTS
from ipolitico.core.constants import ApiParams


class IStateStore(Protocol):
    def get_watermark(self, table: str, column: str) -> str | None: ...
    def get_existing_ids(self, table: str, column: str = "id") -> list[int]: ...


class BaseExtractor(ABC):
    def __init__(self, client: CamaraClient, state_store: IStateStore):
        self.client = client
        self.state_store = state_store

    def _get_last_watermark(self, table: str, column: str) -> str | None:
        """Busca o ponto mais recente (watermark) no banco de dados."""
        return self.state_store.get_watermark(table, column)

    def build_params(self, raw_params: dict) -> dict:
        """
        Constrói o dicionário final de requisição.
        Transforma os Enums em strings e ignora chaves com valor None.
        """
        cleaned_params = {}
        for key, value in raw_params.items():
            if value is not None:
                # Se a chave for Enum, pega o valor string, senão usa a chave como está
                param_key = key.value if isinstance(key, ApiParams) else key
                cleaned_params[param_key] = value

        return cleaned_params

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

    async def execute_concurrently(
        self, items: list, fetch_func, max_workers: int = MAX_CONCURRENT_REQUESTS
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

    # def validate_data(self, schema, data: list):
    #     """Valida a lista de dicionários contra um Schema Pydantic."""
    #     try:
    #         return [schema(**item).dict() for item in data]
    #     except ValidationError as e:
    #         logger.error(f"Erro de contrato na API: {e.json()}")
    #         raise
