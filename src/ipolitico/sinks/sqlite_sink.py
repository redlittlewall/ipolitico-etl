import logging
import sqlite3
from typing import List, Union

import polars as pl

logger = logging.getLogger(__name__)


class SQLiteSink:
    """
    Storage e State Store oficial do pipeline local.
    Implementa o contrato IStateStore implicitamente para injeção de dependência.
    Utiliza padrão Staging Table para operações de UPSERT bulk.
    """

    def __init__(self, db_path: str = "ipolitico.db"):
        self.db_path = db_path
        self._uri = f"sqlite:///{self.db_path}"

    def get_watermark(self, table: str, column: str) -> str | None:
        """Recupera o teto temporal (high-water mark) de uma tabela para cargas incrementais."""
        query = f"SELECT max({column}) FROM {table}"
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                result = cursor.fetchone()[0]
                return result.split("T")[0] if result else None
        except sqlite3.OperationalError:
            # Tabela não existe (First Load)
            return None

    def get_existing_ids(self, table: str, column: str = "id") -> list[int]:
        """Recupera lista de chaves primárias já persistidas para evitar chamadas"""
        """de API desnecessárias."""
        query = f"SELECT {column} FROM {table}"
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pl.read_database(query, conn)
                return df[column].to_list() if not df.is_empty() else []
        except Exception:
            return []

    async def save(
        self, df: pl.DataFrame, table_name: str, unique_keys: Union[str, List[str]] = None
    ) -> None:
        """
        Persiste o DataFrame no SQLite.
        Se `unique_keys` for fornecido, executa uma operação UPSERT (Delete/Insert)
        através de uma tabela de Staging para garantir idempotência.
        """
        if df.is_empty():
            return

        if not unique_keys:
            # Comportamento padrão de Append
            df.write_database(
                table_name=table_name,
                connection=self._uri,
                if_table_exists="append",
                engine="sqlalchemy",
            )
            logger.debug(f"[{table_name}] Append concluído: {df.height} registros.")
            return

        # Padrão Staging Table para UPSERT
        keys = [unique_keys] if isinstance(unique_keys, str) else unique_keys
        staging_table = f"{table_name}_staging"

        # Carga na Staging (substitui se existir lixo de execuções passadas)
        df.write_database(
            table_name=staging_table,
            connection=self._uri,
            if_table_exists="replace",
            engine="sqlalchemy",
        )

        join_conditions = " AND ".join([f"t.{k} = s.{k}" for k in keys])

        delete_query = f"""
            DELETE FROM {table_name} AS t
            WHERE EXISTS (
                SELECT 1 FROM {staging_table} s
                WHERE {join_conditions}
            )
        """
        insert_query = f"INSERT INTO {table_name} SELECT * FROM {staging_table}"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                # Verifica se a tabela target existe
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
                )
                target_exists = cursor.fetchone()

                if target_exists:
                    # Transação UPSERT
                    cursor.execute(delete_query)
                    deleted_rows = cursor.rowcount
                    cursor.execute(insert_query)
                    logger.info(
                        f"[{table_name}] UPSERT: {deleted_rows} atualizados, "
                        f"{df.height - deleted_rows} novos inseridos."
                    )
                else:
                    # First Load: Transforma staging na target
                    cursor.execute(f"ALTER TABLE {staging_table} RENAME TO {table_name}")
                    logger.info(f"[{table_name}] CREATE: {df.height} registros inseridos.")
            finally:
                # Cleanup garantido
                cursor.execute(f"DROP TABLE IF EXISTS {staging_table}")

            conn.commit()
