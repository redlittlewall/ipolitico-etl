import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Protocol

import polars as pl
from tenacity import retry, stop_after_attempt, wait_exponential

from ipolitico.core.config import MAX_CONCURRENT_REQUESTS

logger = logging.getLogger(__name__)


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

    async def execute_pipeline(
        self,
        items: list,
        fetch_func,
        sink_func,
        table_name: str,
        unique_keys: str | list[str] | None = None,
        max_workers: int = MAX_CONCURRENT_REQUESTS,
    ) -> None:
        """
        Motor Producer-Consumer In-Memory com Backpressure.
        Extrai da API e já salva no Banco de Dados em paralelo, sem acumular
        dados massivos na RAM.
        """
        total_items = len(items)
        if total_items == 0:
            return

        job_queue = asyncio.Queue()
        for item in items:
            job_queue.put_nowait(item)

        # [BLINDAGEM ANTI-OOM] Fila de DataFrames com Backpressure.
        # Se o banco de dados (sink) ficar lento, a fila lota e os extratores
        # param de bater na API do governo automaticamente até esvaziar.
        df_queue = asyncio.Queue(maxsize=10)

        processed_count = 0
        log_threshold = max(1, total_items // 10)

        @retry(
            wait=wait_exponential(multiplier=1, min=2, max=16),
            stop=stop_after_attempt(5),
            reraise=True,
        )
        async def worker():
            nonlocal processed_count
            while True:
                try:
                    job = job_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                try:
                    df = await fetch_func(job)
                    if df is not None and not df.is_empty():
                        # O .put() é bloqueante se a fila atingir o maxsize
                        await df_queue.put(df)
                finally:
                    processed_count += 1
                    if processed_count % log_threshold == 0 or processed_count == total_items:
                        percent = (processed_count / total_items) * 100
                        logger.info(
                            f"       [Progresso - {table_name}] {processed_count}/{total_items}"
                            f" ({percent:.1f}%) concluído."
                        )
                    job_queue.task_done()

        async def consumer():
            while True:
                df = await df_queue.get()
                if df is None:
                    df_queue.task_done()
                    break

                try:
                    await sink_func(df, table_name, unique_keys)
                finally:
                    df_queue.task_done()

        consumer_task = asyncio.create_task(consumer())
        workers = [asyncio.create_task(worker()) for _ in range(max_workers)]

        await asyncio.gather(*workers)

        await df_queue.put(None)
        await consumer_task
