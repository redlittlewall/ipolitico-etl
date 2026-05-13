import logging
import sqlite3
from datetime import datetime
from typing import Any, List, Optional, Union

import polars as pl

from ipolitico.core.constants import MedallionLayer
from ipolitico.sinks.base import BaseSink

logger = logging.getLogger(__name__)


class SQLiteSink(BaseSink):
    """
    Armazenamento e controle de estado (State Store) para pipelines locais.
    Implementa o contrato BaseSink. Utiliza o padrão Staging Table para UPSERTs em lote.
    """

    def __init__(self, db_path: str = "data/dbs/ipolitico_state.db"):
        """
        Inicializa o sink do SQLite.

        Args:
            db_path (str): Caminho para o arquivo do banco de dados SQLite.
        """
        self.db_path = db_path
        self._uri = f"sqlite:///{self.db_path}"

    def get_watermark(self, table_name: str, watermark_column: str) -> Optional[str]:
        """
        Consulta o banco de dados para encontrar o maior valor (data mais recente)
        de uma determinada coluna, servindo como marca d'água (watermark) para o ETL.

        Args:
            table_name (str): Nome da tabela destino (ex: 'deputados').
            watermark_column (str): Nome da coluna de data (ex: 'dataHoraInicio').

        Returns:
            Optional[str]: O valor máximo encontrado (formato string ISO) ou None se
                           a tabela não existir ou estiver vazia.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Verifica se a tabela existe (Programação Defensiva)
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
                )
                if not cursor.fetchone():
                    logger.debug(f"StateStore: Tabela '{table_name}' não existe. Retornando None.")
                    return None

                #  Busca a data máxima.

                query = f"SELECT MAX({watermark_column}) FROM {table_name}"
                cursor.execute(query)
                result = cursor.fetchone()

                if result and result[0]:
                    logger.debug(
                        f"StateStore: Watermark encontrado para '{table_name}': {result[0]}"
                    )
                    return str(result[0])

                return None

        except sqlite3.OperationalError as e:
            # Captura erros como "no such column" caso o schema tenha mudado
            logger.warning(
                f"StateStore: Falha ao ler watermark da tabela '{table_name}'. Erro: {e}"
            )
            return None
        except Exception as e:
            logger.error(f"StateStore: Erro inesperado ao consultar watermark: {e}")
            return None

    def get_existing_ids(self, table_name: str, id_column: str) -> List[Any]:
        """
        Recupera uma lista de chaves primárias já persistidas no banco de dados.
        Evita consultas HTTP desnecessárias.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
                )
                if not cursor.fetchone():
                    return []

                cursor.execute(f"SELECT DISTINCT {id_column} FROM {table_name}")
                # Extrai os IDs das tuplas retornadas
                return [row[0] for row in cursor.fetchall() if row[0] is not None]
        except Exception as e:
            logger.warning(f"StateStore: Falha ao recuperar IDs da tabela '{table_name}': {e}")
            return []

    def read_columns(self, table_name: str, columns: List[str]) -> pl.DataFrame:
        """
        Lê colunas específicas de uma tabela de forma ágil para cruzamentos.
        """
        cols = ", ".join(columns)
        query = f"SELECT {cols} FROM {table_name}"
        try:
            with sqlite3.connect(self.db_path) as conn:
                return pl.read_database(query=query, connection=conn)
        except Exception as e:
            logger.error(f"Erro ao ler {columns} de {table_name}: {e}")
            return pl.DataFrame()

    async def save(
        self,
        df: pl.DataFrame,
        table_name: str,
        layer: MedallionLayer = MedallionLayer.BRONZE,
        unique_keys: Optional[Union[str, List[str]]] = None,
        **kwargs: Any,
    ) -> None:
        """
        Persiste o DataFrame no SQLite.
        Utiliza UPSERT (Staging Table) se unique_keys
        forem fornecidas, caso contrário realiza APPEND.
        """
        if df.is_empty():
            logger.debug(f"[{table_name}] DataFrame vazio. Nada para salvar.")
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

        index_name = f"idx_{table_name}_{'_'.join(keys)}"
        index_cols = ", ".join(keys)
        index_query = (
            f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table_name} ({index_cols})"
        )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
                )
                target_exists = cursor.fetchone()

                if target_exists:
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
                    cursor.execute(index_query)
                    logger.debug(
                        f"[{table_name}] CREATE: {df.height} registros "
                        f"inseridos com índice ({index_cols})."
                    )
            finally:
                cursor.execute(f"DROP TABLE IF EXISTS {staging_table}")

            conn.commit()

    async def delete_period(
        self, table: str, start_date: str, end_date: str, date_column: str
    ) -> None:
        """
        Remove registros dentro de uma janela de tempo (idempotência para FULL LOAD).
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
                        f"[{table}] FULL_LOAD: {deleted_rows} registros apagados entre "
                        f"{start_date} e {end_date}."
                    )
        except sqlite3.OperationalError as e:
            logger.debug(f"[{table}] Ignorando deleção. Tabela ainda não existe: {e}")
