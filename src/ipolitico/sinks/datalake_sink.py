import logging
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Union

import polars as pl

logger = logging.getLogger(__name__)


class DataLakeSink:
    """
    Destino de dados orientado a Analytics (OLAP).
    Armazena os dados em formato colunar Parquet, implementando a
    Arquitetura Medallion (Bronze, Silver, Gold).
    """

    def __init__(self, base_dir: str = "data/datalake"):
        """
        Inicializa o sink apontando para o diretório isolado de dados.

        Args:
            base_dir (str): Caminho base do Data Lake. Padrão "data/datalake".
        """
        self.base_dir = Path(base_dir)

    def _get_file_path(self, table_name: str, layer: str) -> Path:
        """
        Gera o caminho do arquivo Parquet garantindo que a pasta da camada exista.

        Args:
            table_name (str): Nome da tabela/entidade.
            layer (str): Camada Medallion ("bronze", "silver", "gold").

        Returns:
            Path: Caminho completo para o arquivo Parquet.
        """
        layer_dir = self.base_dir / layer
        layer_dir.mkdir(parents=True, exist_ok=True)
        return layer_dir / f"{table_name}.parquet"

    async def save(
        self,
        df: pl.DataFrame,
        table_name: str,
        layer: str,
        unique_keys: Optional[Union[str, List[str]]] = None,
    ) -> None:
        """
        Salva o DataFrame em Parquet na camada especificada.
        Se o arquivo já existir, faz a fusão (UPSERT em memória).

        Args:
            df (pl.DataFrame): Dados a serem salvos.
            table_name (str): Nome da tabela destino.
            layer (str): Camada destino ("bronze", "silver", "gold").
            unique_keys (str | List[str], optional): Chaves para deduplicação no UPSERT.
        """
        if df.is_empty():
            return

        df = df.with_columns(pl.lit(datetime.now().isoformat()).alias("captured_at"))
        file_path = self._get_file_path(table_name, layer)

        if not file_path.exists():
            df.write_parquet(file_path)
            logger.debug(
                f"[{table_name} | {layer.upper()}]",
                f"CREATE: Parquet criado com {df.height} registros.",
            )
            return

        existing_df = pl.read_parquet(file_path)
        combined_df = pl.concat([existing_df, df], how="diagonal_relaxed")

        if unique_keys:
            keys = [unique_keys] if isinstance(unique_keys, str) else unique_keys
            combined_df = combined_df.unique(subset=keys, keep="last")

        combined_df.write_parquet(file_path)
        logger.debug(
            f"[{table_name} | {layer.upper()}] UPSERT: Atualizado. "
            f"Total de registros: {combined_df.height}."
        )

    async def delete_period(
        self, table_name: str, layer: str, start_date: str, end_date: str, date_column: str
    ) -> None:
        """
        Remove registros de um período específico recriando o arquivo Parquet.

        Args:
            table_name (str): Nome da tabela.
            layer (str): Camada destino.
            start_date (str): Data inicial (YYYY-MM-DD).
            end_date (str): Data final (YYYY-MM-DD).
            date_column (str): Nome da coluna de data usada para o filtro.
        """
        file_path = self._get_file_path(table_name, layer)
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
                f"[{table_name} | {layer.upper()}] FULL_LOAD: {deleted_rows} registros "
                f"eliminados no período {start_date} a {end_date}."
            )

    def get_existing_ids(self, table_name: str, layer: str, column: str = "id") -> List[Any]:
        """
        Recupera lista de chaves já persistidas no Parquet de forma otimizada.
        """
        file_path = self._get_file_path(table_name, layer)
        if not file_path.exists():
            return []
        try:
            df = pl.read_parquet(file_path, columns=[column])
            return df[column].to_list() if not df.is_empty() else []
        except Exception as e:
            logger.error(f"Erro ao ler IDs do DataLake ({layer}/{table_name}): {e}")
            return []

    def read_columns(self, table_name: str, layer: str, columns: List[str]) -> pl.DataFrame:
        """
        Lê colunas específicas de uma tabela, ideal para cruzamentos rápidos.

        Args:
            table_name (str): Nome da tabela.
            layer (str): Camada origem.
            columns (List[str]): Lista de colunas a serem carregadas na memória.

        Returns:
            pl.DataFrame: DataFrame contendo apenas as colunas solicitadas.
        """
        file_path = self._get_file_path(table_name, layer)
        if not file_path.exists():
            return pl.DataFrame()
        return pl.read_parquet(file_path, columns=columns)
