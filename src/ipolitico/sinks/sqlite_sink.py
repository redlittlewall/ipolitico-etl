import sqlite3

import polars as pl
from ipolitico.sinks.base import BaseSink


class SQLiteSink(BaseSink):
    """
    Cofre SQLite: Salva os DataFrames em um banco de dados relacional local.
    Ideal para uso individual e análise rápida.
    """

    def __init__(self, db_path: str = "ipolitico.db"):
        self.db_path = db_path

    async def save(self, df: pl.DataFrame, table_name: str) -> None:
        """
        Converte o DataFrame do Polars para SQL e salva no banco local.
        """
        # O Polars tem integração nativa para converter para Pandas e então para SQL
        with sqlite3.connect(self.db_path) as conn:
            # O método write_database do Polars facilita muito essa operação
            df.write_database(
                table_name=table_name,
                connection=conn,
                if_table_exists="append",  # Adiciona dados novos aos existentes
            )
