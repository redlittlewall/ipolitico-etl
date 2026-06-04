import asyncio
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import polars as pl

from ipolitico.core.constants import MedallionLayer

logger = logging.getLogger(__name__)


class DataLakeSink:
    """
    Destino de dados orientado a Analytics (OLAP).

    Opera com buffer + flush consolidado para reduzir o número de micro-arquivos
    Parquet. O buffer acumula DataFrames por tabela até atingir threshold de
    tamanho (flush_size_mb) ou tempo (flush_interval_s), ou até flush explícito
    via método flush().

    Args:
        base_dir: Diretório raiz do DataLake.
        flush_size_mb: Tamanho máximo do buffer em MB antes de flush automático.
                       0 desabilita threshold por tamanho.
        flush_interval_s: Intervalo máximo em segundos antes de flush automático.
                          0 desabilita threshold por tempo.
    """

    def __init__(
        self,
        base_dir: str = "data/datalake",
        flush_size_mb: int = 50,
        flush_interval_s: int = 300,
    ):
        self.base_dir = Path(base_dir)
        self.flush_size_mb = flush_size_mb
        self.flush_interval_s = flush_interval_s

        # Buffer interno: key = f"{layer}/{table_name}"
        self._buffers: Dict[str, pl.DataFrame] = {}
        self._lock = asyncio.Lock()
        self._last_flush_time: Dict[str, float] = {}

    # ------------------------------------------------------------------
    #  API Pública
    # ------------------------------------------------------------------

    async def save(
        self,
        df: pl.DataFrame,
        table_name: str,
        layer: str,
        unique_keys: Optional[Union[str, List[str]]] = None,
    ) -> None:
        """
        Acumula o DataFrame no buffer interno. O flush (escrita em Parquet)
        ocorre automaticamente por tamanho/tempo ou via flush() explícito.

        Args:
            df: Dados a serem salvos.
            table_name: Nome da tabela/entidade destino.
            layer: Camada Medallion (bronze, silver, gold).
            unique_keys: Ignorado na ingestão (append-only).
        """
        if df.is_empty():
            return

        # Injeção de auditoria por chunk (antes do buffer)
        df = df.with_columns(pl.lit(datetime.now().isoformat()).alias("captured_at"))

        key = self._buffer_key(table_name, layer)

        async with self._lock:
            if key in self._buffers and self._buffers[key] is not None:
                self._buffers[key] = pl.concat([self._buffers[key], df])
            else:
                self._buffers[key] = df

            await self._maybe_flush(key, table_name, layer)

    async def flush(self, table_name: str, layer: str) -> None:
        """
        Flush explícito: escreve o buffer pendente em Parquet e limpa o buffer.

        Args:
            table_name: Nome da tabela/entidade.
            layer: Camada Medallion.
        """
        key = self._buffer_key(table_name, layer)
        async with self._lock:
            await self._do_flush(key, table_name, layer)

    async def flush_all(self) -> None:
        """
        Flush de todos os buffers pendentes (útil no shutdown do pipeline).
        """
        keys = list(self._buffers.keys())
        for key in keys:
            layer, table_name = key.split("/", 1)
            async with self._lock:
                await self._do_flush(key, table_name, layer)

    # ------------------------------------------------------------------
    #  Métodos de consulta (inalterados)
    # ------------------------------------------------------------------

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
            lazy_df = pl.scan_parquet(layer_dir / "*.parquet")
            series = lazy_df.select(column).unique().collect()[column].drop_nulls()
            return [v for v in series.to_list() if v is not None and v != ""]
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

        if not layer_dir.exists() or not list(layer_dir.glob("*.parquet")):
            logger.debug(f"StateStore (Lake): Nenhum dado anterior encontrado para '{table_name}'.")
            return None

        try:
            lazy_df = pl.scan_parquet(layer_dir / "*.parquet")
            max_val = lazy_df.select(pl.col(watermark_column).max()).collect().item()

            if max_val:
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

    # ------------------------------------------------------------------
    #  Métodos internos
    # ------------------------------------------------------------------

    def _buffer_key(self, table_name: str, layer: str) -> str:
        """Gera chave única para o buffer por tabela + camada."""
        return f"{layer}/{table_name}"

    def _get_file_path(self, table_name: str, layer: str) -> Path:
        """
        Gera um caminho único de arquivo Parquet por flush.
        Evita colisões de concorrência assíncrona.
        """
        layer_dir = self.base_dir / layer / table_name
        layer_dir.mkdir(parents=True, exist_ok=True)

        batch_id = uuid.uuid4().hex[:8]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        return layer_dir / f"lote_{timestamp}_{batch_id}.parquet"

    def _write_parquet(self, df: pl.DataFrame, table_name: str, layer: str) -> None:
        """Escreve 1 arquivo Parquet consolidado a partir do buffer."""
        file_path = self._get_file_path(table_name, layer)
        df.write_parquet(file_path)

        logger.debug(
            f"[{table_name} | {layer.upper()}] FLUSH: {df.height} registros em {file_path.name}."
        )

    async def _maybe_flush(self, key: str, table_name: str, layer: str) -> None:
        """
        Verifica thresholds de tamanho e tempo e faz flush automático se
        necessário. Chamado dentro do lock do save().
        """
        buf = self._buffers.get(key)
        if buf is None:
            return

        # Threshold por tamanho
        if self.flush_size_mb:
            estimated_bytes = buf.estimated_size()
            if estimated_bytes >= self.flush_size_mb * 1024 * 1024:
                logger.debug(
                    f"[{table_name}] Flush automático por tamanho "
                    f"({estimated_bytes / 1024 / 1024:.1f} MB >= {self.flush_size_mb} MB)"
                )
                await self._do_flush(key, table_name, layer)
                return

        # Threshold por tempo
        if self.flush_interval_s:
            last = self._last_flush_time.get(key) or 0.0
            elapsed = time.monotonic() - last
            if elapsed >= self.flush_interval_s:
                buffer_rows = buf.height
                logger.debug(
                    f"[{table_name}] Flush automático por tempo "
                    f"({elapsed:.0f}s >= {self.flush_interval_s}s, {buffer_rows} registros)"
                )
                await self._do_flush(key, table_name, layer)

    async def _do_flush(self, key: str, table_name: str, layer: str) -> None:
        """
        Executa a escrita do buffer em Parquet e limpa o buffer.
        Chamado dentro do lock.
        """
        buf = self._buffers.pop(key, None)
        if buf is not None and not buf.is_empty():
            self._write_parquet(buf, table_name, layer)
        self._last_flush_time[key] = time.monotonic()
