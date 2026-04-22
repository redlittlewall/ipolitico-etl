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
        Salva o DataFrame no SQLite usando o motor do Polars.
        """
        uri = f"sqlite:///{self.db_path}"

        # O Polars usa SQLAlchemy por padrão para o write_database.
        df.write_database(
            table_name=table_name, connection=uri, if_table_exists="append", engine="sqlalchemy"
        )
