import logging
import sqlite3
from datetime import datetime
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
        """
        Recupera lista de chaves primárias já persistidas no banco.
        Evita chamadas HTTP desnecessárias para detalhamentos estáticos.
        """
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
        Utiliza UPSERT (Staging Table) se chaves únicas forem fornecidas, ou APPEND simples.
        """
        if df.is_empty():
            logger.debug(f"ℹ[{table_name}] Nada para salvar (DataFrame vazio).")
            return

        df = df.with_columns(pl.lit(datetime.now().isoformat()).alias("captured_at"))

        if not unique_keys:
            df.write_database(
                table_name=table_name,
                connection=self._uri,
                if_table_exists="append",
                engine="sqlalchemy",
            )
            logger.debug(f"[{table_name}] Append concluído: {df.height} registros.")
            return

        keys = [unique_keys] if isinstance(unique_keys, str) else unique_keys
        staging_table = f"{table_name}_staging"

        df.write_database(
            table_name=staging_table,
            connection=self._uri,
            if_table_exists="replace",
            engine="sqlalchemy",
        )

        join_conditions = " AND ".join([f"t.{k} = s.{k}" for k in keys])
        delete_query = (
            f"DELETE FROM {table_name} AS t WHERE EXISTS "
            f"(SELECT 1 FROM {staging_table} s WHERE {join_conditions})"
        )
        insert_query = f"INSERT INTO {table_name} SELECT * FROM {staging_table}"

        # Criação dinâmica da query de indexação
        index_name = f"idx_{table_name}_{'_'.join(keys)}"
        index_cols = ", ".join(keys)
        index_query = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({index_cols})"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
                )
                target_exists = cursor.fetchone()

                if target_exists:
                    # Garante que o índice existe ANTES do DELETE para performance máxima
                    cursor.execute(index_query)

                    cursor.execute(delete_query)
                    deleted_rows = cursor.rowcount
                    cursor.execute(insert_query)
                    logger.debug(
                        f"[{table_name}] UPSERT: {deleted_rows} atualizados, "
                        f"{df.height - deleted_rows} inseridos."
                    )
                else:
                    cursor.execute(f"ALTER TABLE {staging_table} RENAME TO {table_name}")
                    # Cria o índice logo após a primeira carga
                    cursor.execute(index_query)
                    logger.debug(
                        f"[{table_name}] CREATE: {df.height} registros"
                        f"inseridos com índice ({index_cols})."
                    )
            finally:
                cursor.execute(f"DROP TABLE IF EXISTS {staging_table}")

            conn.commit()

    async def delete_period(self, table: str, start_date: str, end_date: str, date_column: str):
        """
        Elimina registos numa janela temporal (Idempotência de FULL LOAD).
        Inclui ativação estrita de Foreign Keys para deleção em cascata.
        """
        query = f"DELETE FROM {table} WHERE {date_column} >= ? AND {date_column} <= ?"

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON;")

                cursor = conn.cursor()
                cursor.execute(query, (start_date, end_date))

                deleted_rows = cursor.rowcount
                if deleted_rows > 0:
                    logger.warning(
                        f"[{table}] FULL_LOAD: {deleted_rows} registos eliminados no período "
                        f"{start_date} a {end_date}."
                    )

        except sqlite3.OperationalError as e:
            logger.debug(f"[{table}] Ignorando deleção. Tabela ainda não existe: {e}")

    def get_deputados_legislaturas(self) -> dict:
        query = "SELECT id, idLegislaturaInicial, idLegislaturaFinal FROM deputados"
        try:
            df = pl.read_database(query, self.conn)
            return {row["id"]: row for row in df.to_dicts()}
        except Exception:
            return {}
