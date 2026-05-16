"""Leituras out-of-core no data lake (Polars/DuckDB) — sem regras de domínio."""

import logging
from pathlib import Path
from typing import Any, List

import duckdb
from ipolitico.core.constants import DomainType

logger = logging.getLogger(__name__)


class DataLakeRepository:
    """
    Repositório de leitura para Parquet no layout Medallion.
    Centraliza consultas ad hoc que antes viviam no PipelineManager.
    """

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)

    @classmethod
    def from_sink(cls, sink: Any) -> "DataLakeRepository":
        """Constroi a partir de DataLakeSink (atributo base_dir)."""
        return cls(sink.base_dir)

    def list_deputy_ids_for_legislature_bounds(
        self,
        leg_start: int,
        leg_end: int,
        silver_fallback_ids: List[Any],
    ) -> List[Any]:
        """
        IDs distintos de deputados cuja idLegislatura está no intervalo.

        Se gold/deputados.parquet existir, usa DuckDB; senão retorna fallback.
        """
        parquet_path = self.base_dir / "gold" / DomainType.DEPUTADOS.value / "deputados.parquet"
        if not parquet_path.exists():
            logger.warning(
                "[DataLakeRepository] Gold deputados ausente em %s; usando fallback Silver.",
                parquet_path,
            )
            return silver_fallback_ids

        try:
            path_sql = str(parquet_path).replace("'", "''")
            query = (
                f"SELECT DISTINCT id FROM read_parquet('{path_sql}') "
                f"WHERE idLegislatura BETWEEN {leg_start} AND {leg_end}"
            )
            con = duckdb.connect(database=":memory:")
            try:
                df = con.execute(query).df()
            finally:
                con.close()
            ids = df["id"].tolist() if not df.empty else []
            logger.info(
                "[DataLakeRepository] DuckDB: %s deputados (leg %s..%s).",
                len(ids),
                leg_start,
                leg_end,
            )
            return ids
        except Exception as e:
            logger.error(
                "[DataLakeRepository] Falha DuckDB em deputados gold: %s. Fallback Silver.",
                e,
            )
            return silver_fallback_ids

    def list_ids(self, table_name: str, layer: str, column: str = "id") -> List[Any]:
        """IDs distintos em silver/<tabela> ou gold/<tabela>/<tabela>.parquet."""
        import polars as pl

        layer_dir = self.base_dir / layer / table_name
        if not layer_dir.exists():
            return []

        gold_file = layer_dir / f"{table_name}.parquet"
        if gold_file.exists():
            try:
                series = pl.scan_parquet(gold_file).select(column).unique().collect()[column]
                return [v for v in series.drop_nulls().to_list() if v is not None and v != ""]
            except Exception as e:
                logger.error(
                    "[DataLakeRepository] Falha ao ler %s de %s: %s",
                    column,
                    gold_file,
                    e,
                )
                return []

        if not list(layer_dir.glob("*.parquet")):
            return []

        try:
            series = (
                pl.scan_parquet(layer_dir / "*.parquet").select(column).unique().collect()[column]
            )
            return [v for v in series.drop_nulls().to_list() if v is not None and v != ""]
        except Exception as e:
            logger.error(
                "[DataLakeRepository] Falha ao listar %s em %s/%s: %s",
                column,
                layer,
                table_name,
                e,
            )
            return []

    def list_votacao_ids_silver_or_gold(self) -> List[Any]:
        """IDs de votações para enfileirar votos (silver, depois gold)."""
        ids = self.list_ids(DomainType.VOTACOES.value, "silver", "id")
        if ids:
            logger.info("[DataLakeRepository] %s IDs de votações na Silver.", len(ids))
            return ids
        ids = self.list_ids(DomainType.VOTACOES.value, "gold", "id")
        if ids:
            logger.info("[DataLakeRepository] %s IDs de votações na Gold (fallback).", len(ids))
        return ids
