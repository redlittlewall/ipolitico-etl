import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Union

import polars as pl

from ipolitico.core.constants import MedallionLayer

logger = logging.getLogger(__name__)


class DataLakeSink:
    """
    Destino de dados orientado a Analytics (OLAP).
    Opera estritamente no padrão Append-Only durante a ingestão para garantir
    velocidade e evitar Race Conditions/Locks.
    """

    def __init__(self, base_dir: str = "data/datalake"):
        """
        Inicializa o sink apontando para o diretório isolado de dados.
        """
        self.base_dir = Path(base_dir)

    def _get_file_path(self, table_name: str, layer: str) -> Path:
        """
        Gera um caminho único de arquivo Parquet (Micro-batching) por requisição.
        Evita colisões de concorrência assíncrona.
        """
        layer_dir = self.base_dir / layer / table_name
        layer_dir.mkdir(parents=True, exist_ok=True)

        # Gera um ID único e timestamp para o lote
        batch_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        return layer_dir / f"lote_{timestamp}_{batch_id}.parquet"

    async def save(
        self,
        df: pl.DataFrame,
        table_name: str,
        layer: str,
        unique_keys: Optional[Union[str, List[str]]] = None,
    ) -> None:
        """
        Salva o DataFrame em Parquet (Append-Only).
        Ignora unique_keys na ingestão; a desduplicação será feita no Optimizer.
        """
        if df.is_empty():
            return

        # Injeção da trilha de auditoria e governança
        df = df.with_columns(pl.lit(datetime.now().isoformat()).alias("captured_at"))

        file_path = self._get_file_path(table_name, layer)
        df.write_parquet(file_path)

        logger.debug(
            f"[{table_name} | {layer.upper()}] APPEND: Lote gravado ({df.height} registros)."
        )

    async def delete_period(self, *args, **kwargs) -> None:
        """
        Desabilitado no padrão Append-Only.
        Deleções lógicas devem ocorrer na camada Gold.
        """
        pass

    def get_existing_ids(self, table_name: str, layer: str, column: str = "id") -> List[Any]:
        """
        Recupera chaves usando Polars Lazy API (scan) para evitar Out-Of-Memory.
        """
        layer_dir = self.base_dir / layer / table_name
        if not layer_dir.exists() or not list(layer_dir.glob("*.parquet")):
            return []

        try:
            # scan_parquet lê apenas os metadados e a coluna específica
            lazy_df = pl.scan_parquet(layer_dir / "*.parquet")
            return lazy_df.select(column).unique().collect()[column].to_list()
        except Exception as e:
            logger.error(f"Erro ao ler IDs do DataLake ({layer}/{table_name}): {e}")
            return []

    def read_columns(self, table_name: str, layer: str, columns: List[str]) -> pl.DataFrame:
        """
        Lê colunas específicas otimizadas via Lazy Evaluation.
        """
        layer_dir = self.base_dir / layer / table_name
        if not layer_dir.exists() or not list(layer_dir.glob("*.parquet")):
            return pl.DataFrame()

        return pl.scan_parquet(layer_dir / "*.parquet").select(columns).collect()

    def get_watermark(self, table_name: str, watermark_column: str) -> Optional[str]:
        """
        Descobre a data mais recente processada varrendo os metadados dos Parquets.
        Usa Lazy Evaluation (Out-of-Core) para não estourar a RAM.
        """
        layer_dir = self.base_dir / MedallionLayer.SILVER / table_name

        # Se a pasta não existe ou está vazia, é a primeira vez rodando (Full Load)
        if not layer_dir.exists() or not list(layer_dir.glob("*.parquet")):
            logger.debug(f"StateStore (Lake): Nenhum dado anterior encontrado para '{table_name}'.")
            return None

        try:
            # Varre todos os arquivos sem jogar na memória
            lazy_df = pl.scan_parquet(layer_dir / "*.parquet")

            # Executa a agregação (MAX)
            max_val = lazy_df.select(pl.col(watermark_column).max()).collect().item()

            if max_val:
                # O Manager espera uma string em formato ISO
                data_iso = str(max_val).replace(" ", "T")
                logger.debug(
                    f"StateStore (Lake): Watermark encontrado para '{table_name}': {data_iso}"
                )
                return data_iso

            return None

        except Exception as e:
            logger.warning(
                f"StateStore (Lake): Falha ao ler watermark da tabela '{table_name}'. Erro: {e}"
            )
            return None
