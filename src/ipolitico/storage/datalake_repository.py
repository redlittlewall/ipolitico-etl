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
