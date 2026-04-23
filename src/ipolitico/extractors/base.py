import asyncio
from abc import ABC, abstractmethod
from typing import Protocol

import polars as pl
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ipolitico.core.config import MAX_CONCURRENT_REQUESTS


class IStateStore(Protocol):
    def get_watermark(self, table: str, column: str) -> str | None: ...
    def get_existing_ids(self, table: str, column: str = "id") -> list[int]: ...


class BaseExtractor(ABC):
    """
    Base Universal. Totalmente cega em relação a APIs, paginações ou formatos de arquivo.
    Fornece apenas os utilitários fundamentais (Concorrência e Estado).
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
        desc: str = "Processando",
    ) -> pl.DataFrame:
        """Motor de concorrência genérico. Roda tarefas assíncronas em paralelo com segurança."""
        if not items:
            return pl.DataFrame()

        semaforo = asyncio.Semaphore(max_workers)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            task_id = progress.add_task(f"[cyan]{desc}...", total=len(items))

            async def bounded_fetch(item):
                async with semaforo:
                    try:
                        res = await fetch_func(item)
                        return res
                    finally:
                        progress.advance(task_id)

            tarefas = [bounded_fetch(item) for item in items]
            resultados = await asyncio.gather(*tarefas)

        frames = [r for r in resultados if isinstance(r, pl.DataFrame) and not r.is_empty()]
        return pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame()
