import sqlite3
from abc import ABC, abstractmethod

import polars as pl

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
