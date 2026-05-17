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
            silver_ids = self.list_deputy_ids_for_legislature_bounds_from_silver(
                leg_start, leg_end, silver_fallback_ids
            )
            if silver_ids is not silver_fallback_ids and silver_ids:
                return silver_ids
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

    def list_deputy_ids_for_legislature_bounds_from_silver(
        self,
        leg_start: int,
        leg_end: int,
        silver_fallback_ids: List[Any],
    ) -> List[Any]:
        """Filtra Silver de deputados por idLegislatura quando Gold ainda não existe."""
        import polars as pl

        layer_dir = self.base_dir / "silver" / DomainType.DEPUTADOS.value
        if not layer_dir.exists() or not list(layer_dir.glob("*.parquet")):
            return silver_fallback_ids

        try:
            schema = pl.scan_parquet(layer_dir / "*.parquet").collect_schema()
            if "idLegislatura" not in schema.names():
                return silver_fallback_ids

            series = (
                pl.scan_parquet(layer_dir / "*.parquet")
                .filter(
                    (pl.col("idLegislatura") >= leg_start) & (pl.col("idLegislatura") <= leg_end)
                )
                .select("id")
                .unique()
                .collect()["id"]
            )
            ids = [v for v in series.drop_nulls().to_list() if v is not None]
            if ids:
                logger.info(
                    "[DataLakeRepository] Silver deputados: %s IDs (leg %s..%s).",
                    len(ids),
                    leg_start,
                    leg_end,
                )
                return ids
        except Exception as e:
            logger.warning("[DataLakeRepository] Filtro Silver deputados por leg: %s", e)
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

    def list_votacao_ids_silver_or_gold(
        self,
        start_iso: str | None = None,
        end_iso: str | None = None,
    ) -> List[Any]:
        """
        IDs de votações para enfileirar votos (silver, depois gold).

        Com start_iso/end_iso, restringe pela coluna ``data`` à janela efetiva.
        """
        if start_iso and end_iso:
            ids = self._list_votacao_ids_in_window("silver", start_iso, end_iso)
            if ids:
                logger.info(
                    "[DataLakeRepository] %s votações na Silver na janela %s..%s.",
                    len(ids),
                    start_iso[:10],
                    end_iso[:10],
                )
                return ids
            ids = self._list_votacao_ids_in_window("gold", start_iso, end_iso)
            if ids:
                logger.info(
                    "[DataLakeRepository] %s votações na Gold na janela %s..%s.",
                    len(ids),
                    start_iso[:10],
                    end_iso[:10],
                )
            return ids

        ids = self.list_ids(DomainType.VOTACOES.value, "silver", "id")
        if ids:
            logger.info("[DataLakeRepository] %s IDs de votações na Silver.", len(ids))
            return ids
        ids = self.list_ids(DomainType.VOTACOES.value, "gold", "id")
        if ids:
            logger.info("[DataLakeRepository] %s IDs de votações na Gold (fallback).", len(ids))
        return ids

    def _list_votacao_ids_in_window(self, layer: str, start_iso: str, end_iso: str) -> List[Any]:
        import polars as pl

        lo, hi = start_iso[:10], end_iso[:10]
        table = DomainType.VOTACOES.value
        layer_dir = self.base_dir / layer / table
        if not layer_dir.exists():
            return []

        gold_file = layer_dir / f"{table}.parquet"
        paths = [gold_file] if gold_file.exists() else list(layer_dir.glob("*.parquet"))
        if not paths:
            return []

        try:
            lazy = pl.scan_parquet(paths)
            schema = lazy.collect_schema()
            if "data" not in schema.names():
                return self.list_ids(table, layer, "id")

            dtype = schema["data"]
            is_dt = dtype == pl.Datetime or str(dtype).lower().startswith("datetime")
            day_col = (
                pl.col("data").dt.strftime("%Y-%m-%d")
                if is_dt
                else pl.col("data").cast(pl.Utf8, strict=False).str.slice(0, 10)
            )
            series = (
                lazy.filter((day_col >= lo) & (day_col <= hi)).select("id").unique().collect()["id"]
            )
            return [v for v in series.drop_nulls().to_list() if v is not None and v != ""]
        except Exception as e:
            logger.error(
                "[DataLakeRepository] Falha ao filtrar votações por janela em %s: %s",
                layer,
                e,
            )
            return []

    def list_votacao_ids_with_votos_materialized(self) -> set[Any]:
        """votacao_id distintos já presentes em votos (Silver ou Gold)."""
        ids = set(self.list_ids(DomainType.VOTOS.value, "silver", "votacao_id"))
        ids.update(self.list_ids(DomainType.VOTOS.value, "gold", "votacao_id"))
        return ids

    def list_deputy_ids_in_child_table(self, table_name: str) -> set[Any]:
        """Deputados que já têm linhas em profissoes/ocupacoes na Silver."""
        return set(self.list_ids(table_name, "silver", "id_deputado"))

    def list_proposicao_ids_silver_or_gold(
        self,
        start_iso: str | None = None,
        end_iso: str | None = None,
    ) -> List[Any]:
        """IDs de proposições na janela (coluna dataApresentacao)."""
        if start_iso and end_iso:
            ids = self._list_proposicao_ids_in_window("silver", start_iso, end_iso)
            if ids:
                return ids
            return self._list_proposicao_ids_in_window("gold", start_iso, end_iso)
        return self.list_ids(DomainType.PROPOSICOES.value, "silver", "id") or self.list_ids(
            DomainType.PROPOSICOES.value, "gold", "id"
        )

    def _list_proposicao_ids_in_window(self, layer: str, start_iso: str, end_iso: str) -> List[Any]:
        import polars as pl

        lo, hi = start_iso[:10], end_iso[:10]
        table = DomainType.PROPOSICOES.value
        layer_dir = self.base_dir / layer / table
        if not layer_dir.exists():
            return []

        gold_file = layer_dir / f"{table}.parquet"
        paths = [gold_file] if gold_file.exists() else list(layer_dir.glob("*.parquet"))
        if not paths:
            return []

        try:
            lazy = pl.scan_parquet(paths)
            schema = lazy.collect_schema()
            if "dataApresentacao" not in schema.names():
                return self.list_ids(table, layer, "id")

            dtype = schema["dataApresentacao"]
            is_dt = dtype == pl.Datetime or str(dtype).lower().startswith("datetime")
            day_col = (
                pl.col("dataApresentacao").dt.strftime("%Y-%m-%d")
                if is_dt
                else pl.col("dataApresentacao").cast(pl.Utf8, strict=False).str.slice(0, 10)
            )
            series = (
                lazy.filter((day_col >= lo) & (day_col <= hi)).select("id").unique().collect()["id"]
            )
            return [v for v in series.drop_nulls().to_list() if v is not None]
        except Exception as e:
            logger.error("[DataLakeRepository] Falha ao filtrar proposições: %s", e)
            return []

    def list_proposicao_ids_with_child_materialized(self, table_name: str) -> set[Any]:
        return set(self.list_ids(table_name, "silver", "id_proposicao")) | set(
            self.list_ids(table_name, "gold", "id_proposicao")
        )

    def list_orgao_ids_silver_or_gold(self) -> List[Any]:
        return self.list_ids(DomainType.ORGAOS.value, "silver", "id") or self.list_ids(
            DomainType.ORGAOS.value, "gold", "id"
        )

    def list_frente_ids_silver_or_gold(self, legislatura_id: int | None = None) -> List[Any]:
        import polars as pl

        table = DomainType.FRENTES.value
        for layer in ("silver", "gold"):
            layer_dir = self.base_dir / layer / table
            if not layer_dir.exists():
                continue
            gold_file = layer_dir / f"{table}.parquet"
            paths = [gold_file] if gold_file.exists() else list(layer_dir.glob("*.parquet"))
            if not paths:
                continue
            try:
                lazy = pl.scan_parquet(paths)
                schema = lazy.collect_schema()
                if legislatura_id is not None and "idLegislatura" in schema.names():
                    series = (
                        lazy.filter(pl.col("idLegislatura") == legislatura_id)
                        .select("id")
                        .unique()
                        .collect()["id"]
                    )
                else:
                    series = lazy.select("id").unique().collect()["id"]
                ids = [v for v in series.drop_nulls().to_list() if v is not None]
                if ids:
                    return ids
            except Exception as e:
                logger.error("[DataLakeRepository] Falha ao listar frentes: %s", e)
        return []

    def list_votacao_ids_with_orientacoes_materialized(self) -> set[Any]:
        return set(self.list_ids(DomainType.ORIENTACOES.value, "silver", "votacao_id")) | set(
            self.list_ids(DomainType.ORIENTACOES.value, "gold", "votacao_id")
        )

    def list_entity_ids_with_child_materialized(
        self, table_name: str, parent_id_column: str
    ) -> set[Any]:
        return set(self.list_ids(table_name, "silver", parent_id_column)) | set(
            self.list_ids(table_name, "gold", parent_id_column)
        )

    def list_evento_ids_silver_or_gold(
        self,
        start_iso: str | None = None,
        end_iso: str | None = None,
    ) -> List[Any]:
        if start_iso and end_iso:
            ids = self._list_evento_ids_in_window("silver", start_iso, end_iso)
            if ids:
                return ids
            return self._list_evento_ids_in_window("gold", start_iso, end_iso)
        return self.list_ids(DomainType.EVENTOS.value, "silver", "id") or self.list_ids(
            DomainType.EVENTOS.value, "gold", "id"
        )

    def _list_evento_ids_in_window(self, layer: str, start_iso: str, end_iso: str) -> List[Any]:
        import polars as pl

        lo, hi = start_iso[:10], end_iso[:10]
        table = DomainType.EVENTOS.value
        layer_dir = self.base_dir / layer / table
        if not layer_dir.exists():
            return []

        gold_file = layer_dir / f"{table}.parquet"
        paths = [gold_file] if gold_file.exists() else list(layer_dir.glob("*.parquet"))
        if not paths:
            return []

        try:
            lazy = pl.scan_parquet(paths)
            schema = lazy.collect_schema()
            if "dataHoraInicio" not in schema.names():
                return self.list_ids(table, layer, "id")

            dtype = schema["dataHoraInicio"]
            is_dt = dtype == pl.Datetime or str(dtype).lower().startswith("datetime")
            day_col = (
                pl.col("dataHoraInicio").dt.strftime("%Y-%m-%d")
                if is_dt
                else pl.col("dataHoraInicio").cast(pl.Utf8, strict=False).str.slice(0, 10)
            )
            series = (
                lazy.filter((day_col >= lo) & (day_col <= hi)).select("id").unique().collect()["id"]
            )
            return [v for v in series.drop_nulls().to_list() if v is not None]
        except Exception as e:
            logger.error("[DataLakeRepository] Falha ao filtrar eventos: %s", e)
            return []

    def list_partido_ids_silver_or_gold(self) -> List[Any]:
        return self.list_ids(DomainType.PARTIDOS.value, "silver", "id") or self.list_ids(
            DomainType.PARTIDOS.value, "gold", "id"
        )

    def list_grupo_ids_silver_or_gold(self) -> List[Any]:
        return self.list_ids(DomainType.GRUPOS.value, "silver", "id") or self.list_ids(
            DomainType.GRUPOS.value, "gold", "id"
        )

    def list_bloco_ids_silver_or_gold(self, legislatura_id: int | None = None) -> List[Any]:
        import polars as pl

        table = DomainType.BLOCOS.value
        for layer in ("silver", "gold"):
            layer_dir = self.base_dir / layer / table
            if not layer_dir.exists():
                continue
            gold_file = layer_dir / f"{table}.parquet"
            paths = [gold_file] if gold_file.exists() else list(layer_dir.glob("*.parquet"))
            if not paths:
                continue
            try:
                lazy = pl.scan_parquet(paths)
                schema = lazy.collect_schema()
                if legislatura_id is not None and "idLegislatura" in schema.names():
                    series = (
                        lazy.filter(pl.col("idLegislatura") == legislatura_id)
                        .select("id")
                        .unique()
                        .collect()["id"]
                    )
                else:
                    series = lazy.select("id").unique().collect()["id"]
                ids = [v for v in series.drop_nulls().to_list() if v is not None]
                if ids:
                    return ids
            except Exception as e:
                logger.error("[DataLakeRepository] Falha ao listar blocos: %s", e)
        return []

    def list_deputy_expense_year_pairs(self) -> set[tuple[Any, int]]:
        """Pares (id_deputado, ano) já materializados na Silver de despesas."""
        import polars as pl

        layer_dir = self.base_dir / "silver" / DomainType.DESPESAS.value
        if not layer_dir.exists() or not list(layer_dir.glob("*.parquet")):
            return set()

        try:
            df = (
                pl.scan_parquet(layer_dir / "*.parquet")
                .select("id_deputado", "ano")
                .unique()
                .collect()
            )
            return {(row[0], int(row[1])) for row in df.iter_rows() if row[0] is not None}
        except Exception as e:
            logger.warning("[DataLakeRepository] Não foi possível listar pares despesas: %s", e)
            return set()
