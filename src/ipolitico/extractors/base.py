import asyncio
from abc import ABC, abstractmethod
from typing import Protocol

import polars as pl
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ipolitico.core.config import MAX_CONCURRENT_REQUESTS


class IStateStore(Protocol):
    def get_watermark(self, table: str, column: str) -> str | None: ...
    def get_existing_ids(self, table: str, column: str = "id") -> list[int]: ...


class BaseExtractor(ABC):
    """
    Base Universal do iPolitico.
    Fornece o motor assíncrono estrito com tolerância a falhas (Exponential Backoff).
    Totalmente agnóstico: não conhece a API do governo nem o banco de dados local.
    """

    def __init__(self, state_store: IStateStore):
        self.state_store = state_store

    def _get_last_watermark(self, table: str, column: str) -> str | None:
        return self.state_store.get_watermark(table, column)

    @abstractmethod
    async def extract(self, **kwargs) -> pl.DataFrame:
        pass

    async def execute_concurrently(
        self,
        items: list,
        fetch_func,
        max_workers: int = MAX_CONCURRENT_REQUESTS,
        desc: str = "",
    ) -> pl.DataFrame:
        """
        Motor de concorrência genérico.
        Executa tarefas em paralelo respeitando limites de requisição e implementando
        retry automático para proteger contra instabilidades de rede.
        """
        if not items:
            return pl.DataFrame()

        semaforo = asyncio.Semaphore(max_workers)

        @retry(
            wait=wait_exponential(multiplier=1, min=2, max=16),
            stop=stop_after_attempt(5),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )
        async def bounded_fetch(item):
            async with semaforo:
                return await fetch_func(item)

        tarefas = [bounded_fetch(item) for item in items]
        resultados = await asyncio.gather(*tarefas, return_exceptions=False)

        frames = [r for r in resultados if isinstance(r, pl.DataFrame) and not r.is_empty()]
        return pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame()
