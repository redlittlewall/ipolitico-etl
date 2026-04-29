import logging
from datetime import datetime
from pathlib import Path
from typing import List, Union

import polars as pl

logger = logging.getLogger(__name__)


class DataLakeSink:
    """
    Destino de dados orientado a Analytics (OLAP).
    Armazena os dados em formato colunar Parquet, ideal para consultas pesadas
    com DuckDB ou leitura massiva via APIs.
    """

    def __init__(self, base_dir: str = "datalake"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, table_name: str) -> Path:
        return self.base_dir / f"{table_name}.parquet"

    async def save(
        self, df: pl.DataFrame, table_name: str, unique_keys: Union[str, List[str]] = None
    ) -> None:
        """
        Salva o DataFrame em Parquet. Se o arquivo já existir, faz a fusão (UPSERT em memória).
        """
        if df.is_empty():
            return

        df = df.with_columns(pl.lit(datetime.now().isoformat()).alias("captured_at"))
        file_path = self._get_file_path(table_name)

        if not file_path.exists():
            # First Load
            df.write_parquet(file_path)
            logger.debug(
                f"[{table_name}] CREATE: DataLake Parquet criado com {df.height} registros."
            )
            return

        # Incremental Load (UPSERT em Memória com Polars)
        existing_df = pl.read_parquet(file_path)
        combined_df = pl.concat([existing_df, df], how="diagonal_relaxed")

        if unique_keys:
            keys = [unique_keys] if isinstance(unique_keys, str) else unique_keys
            # Mantém o registro mais recente (o que acabou de chegar) em caso de chaves iguais
            combined_df = combined_df.unique(subset=keys, keep="last")

        combined_df.write_parquet(file_path)
        logger.debug(
            f"[{table_name}] UPSERT Parquet: Arquivo atualizado. "
            f"Total de registros agora: {combined_df.height}."
        )

    async def delete_period(self, table: str, start_date: str, end_date: str, date_column: str):
        """
        Remove registros de um período específico recriando o arquivo Parquet sem eles.
        """
        file_path = self._get_file_path(table)
        if not file_path.exists():
            return

        df = pl.read_parquet(file_path)

        df_filtered = df.filter(
            (pl.col(date_column).cast(pl.String).str.slice(0, 10) < start_date)
            | (pl.col(date_column).cast(pl.String).str.slice(0, 10) > end_date)
        )

        deleted_rows = df.height - df_filtered.height
        if deleted_rows > 0:
            df_filtered.write_parquet(file_path)
            logger.warning(
                f"[{table}] FULL_LOAD (DataLake): {deleted_rows} registos "
                f"eliminados no período {start_date} a {end_date}."
            )
