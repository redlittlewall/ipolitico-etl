"""Leituras out-of-core no data lake (Polars/DuckDB) — sem regras de domínio."""

import logging
from pathlib import Path
from typing import Any, List, Optional

import duckdb

from ipolitico.core.constants import DomainType
from ipolitico.storage.state_store import StateStore

logger = logging.getLogger(__name__)


class DataLakeRepository(StateStore):
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
                series = (
                    pl.scan_parquet(gold_file, extra_columns="ignore")
                    .select(column)
                    .unique()
                    .collect()[column]
                )
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
                pl.scan_parquet(layer_dir / "*.parquet", extra_columns="ignore")
                .select(column)
                .unique()
                .collect()[column]
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

    def get_existing_ids(
        self,
        table_name: str,
        layer: str,
        column: str = "id",
    ) -> List[Any]:
        """
        Retorna valores distintos de uma coluna de ID persistidos no Data Lake.

        Implementa o contrato StateStore. Busca na camada especificada; se não
        encontrar, tenta a camada gold como fallback.

        Args:
            table_name: Nome da tabela/domínio.
            layer: Camada Medallion ('silver', 'gold').
            column: Nome da coluna de ID (padrão 'id').

        Returns:
            Lista de valores distintos encontrados ou lista vazia.
        """
        ids = self.list_ids(table_name, layer, column)
        if not ids:
            ids = self.list_ids(table_name, "gold", column)
        return ids

    def get_watermark(self, table_name: str, watermark_column: str) -> Optional[str]:
        """
        Retorna o maior valor da coluna watermark nos Parquet (Silver ou Gold).

        Tenta a Silver primeiro (dado bruto); se não encontrar ou estiver vazia,
        cai na Gold como fallback. Isto permite que execuções incrementais no
        GitHub Actions funcionem mesmo sem a camada Silver presente (apenas Gold).

        Args:
            table_name: Nome da tabela/domínio (ex: 'despesas', 'eventos').
            watermark_column: Nome da coluna que serve como marca d'água
                (ex: 'dataDocumento', 'dataHoraInicio').

        Returns:
            Valor máximo em string ISO, ou None se não houver dados em
            nenhuma camada.
        """
        import polars as pl

        for layer in ("silver", "gold"):
            layer_dir = self.base_dir / layer / table_name
            if not layer_dir.exists():
                continue

            if layer == "gold":
                parquet_file = layer_dir / f"{table_name}.parquet"
                paths = [parquet_file] if parquet_file.exists() else []
            else:
                paths = list(layer_dir.glob("*.parquet"))

            if not paths:
                continue

            try:
                lazy_df = pl.scan_parquet(paths)
                schema = lazy_df.collect_schema()
                if watermark_column not in schema.names():
                    logger.warning(
                        "[DataLakeRepository] Coluna watermark '%s' ausente em %s/%s.",
                        watermark_column,
                        layer,
                        table_name,
                    )
                    continue

                max_val = lazy_df.select(pl.col(watermark_column).max()).collect().item()
                if max_val is not None:
                    return str(max_val).replace(" ", "T")
            except Exception as e:
                logger.warning(
                    "[DataLakeRepository] Falha ao ler watermark de '%s' em %s/%s: %s",
                    table_name,
                    layer,
                    watermark_column,
                    e,
                )

        return None

    def list_votacao_ids_silver_or_gold(
        self,
        start_iso: str | None = None,
        end_iso: str | None = None,
    ) -> List[Any]:
        """
        IDs de votações para enfileirar votos (silver, depois gold).

        Com start_iso/end_iso, restringe pela coluna ``data`` à janela efetiva.
        """
        table = DomainType.VOTACOES.value
        if start_iso and end_iso:
            ids = self._list_ids_in_window(table, "data", "silver", start_iso, end_iso)
            if ids:
                logger.info(
                    "[DataLakeRepository] %s votações na Silver na janela %s..%s.",
                    len(ids),
                    start_iso[:10],
                    end_iso[:10],
                )
                return ids
            ids = self._list_ids_in_window(table, "data", "gold", start_iso, end_iso)
            if ids:
                logger.info(
                    "[DataLakeRepository] %s votações na Gold na janela %s..%s.",
                    len(ids),
                    start_iso[:10],
                    end_iso[:10],
                )
            return ids

        ids = self.list_ids(table, "silver", "id")
        if ids:
            logger.info("[DataLakeRepository] %s IDs de votações na Silver.", len(ids))
            return ids
        ids = self.list_ids(table, "gold", "id")
        if ids:
            logger.info("[DataLakeRepository] %s IDs de votações na Gold (fallback).", len(ids))
        return ids

    def _list_ids_in_window(
        self,
        table_name: str,
        date_column: str,
        layer: str,
        start_iso: str,
        end_iso: str,
    ) -> List[Any]:
        """IDs da tabela filtrados por janela temporal (coluna de data), out-of-core.

        Args:
            table_name: Nome do domínio (ex: 'votacoes', 'proposicoes').
            date_column: Nome da coluna de data para filtrar (ex: 'data', 'dataApresentacao').
            layer: Camada Medallion ('silver', 'gold').
            start_iso: Início da janela (ISO 8601).
            end_iso: Fim da janela (ISO 8601).

        Returns:
            Lista de IDs distintos no intervalo, ou lista vazia se não houver dados.
        """
        import polars as pl

        lo, hi = start_iso[:10], end_iso[:10]
        layer_dir = self.base_dir / layer / table_name
        if not layer_dir.exists():
            return []

        gold_file = layer_dir / f"{table_name}.parquet"
        paths = [gold_file] if gold_file.exists() else list(layer_dir.glob("*.parquet"))
        if not paths:
            return []

        try:
            lazy = pl.scan_parquet(paths)
            schema = lazy.collect_schema()
            if date_column not in schema.names():
                return self.list_ids(table_name, layer, "id")

            dtype = schema[date_column]
            is_dt = dtype == pl.Datetime or str(dtype).lower().startswith("datetime")
            day_col = (
                pl.col(date_column).dt.strftime("%Y-%m-%d")
                if is_dt
                else pl.col(date_column).cast(pl.Utf8, strict=False).str.slice(0, 10)
            )
            series = (
                lazy.filter((day_col >= lo) & (day_col <= hi)).select("id").unique().collect()["id"]
            )
            return [v for v in series.drop_nulls().to_list() if v is not None and v != ""]
        except Exception as e:
            logger.error(
                "[DataLakeRepository] Falha ao filtrar %s por %s em %s: %s",
                table_name,
                date_column,
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
            ids = self._list_ids_in_window(
                DomainType.PROPOSICOES.value, "dataApresentacao", "silver", start_iso, end_iso
            )
            if ids:
                return ids
            return self._list_ids_in_window(
                DomainType.PROPOSICOES.value, "dataApresentacao", "gold", start_iso, end_iso
            )
        return self.list_ids(DomainType.PROPOSICOES.value, "silver", "id") or self.list_ids(
            DomainType.PROPOSICOES.value, "gold", "id"
        )

    def list_proposicao_ids_with_child_materialized(self, table_name: str) -> set[Any]:
        return set(self.list_ids(table_name, "silver", "id_proposicao")) | set(
            self.list_ids(table_name, "gold", "id_proposicao")
        )

    def list_orgao_ids_silver_or_gold(self) -> List[Any]:
        return self.list_ids(DomainType.ORGAOS.value, "silver", "id") or self.list_ids(
            DomainType.ORGAOS.value, "gold", "id"
        )

    def list_orgao_ids_in_window(self, start_iso: str, end_iso: str) -> List[Any]:
        """
        IDs de órgãos ativos na janela temporal, usando ``dataInicio``/``dataFim``.

        Faz DuckDB JOIN entre ``gold/orgaos`` e ``gold/orgaos_detalhe`` para
        filtrar apenas órgãos que estavam ativos na janela (``dataInicio <= end``
        AND (``dataFim IS NULL`` OR ``dataFim >= start``)). Isto elimina chamadas
        de API desnecessárias para órgãos extintos antes da janela.

        Args:
            start_iso: Início da janela (ISO 8601).
            end_iso: Fim da janela (ISO 8601).

        Returns:
            Lista de IDs de órgãos ativos na janela, ou lista vazia.
        """
        lo, hi = start_iso[:10], end_iso[:10]
        con = duckdb.connect(database=":memory:")
        try:
            # Usa gold/orgaos e gold/orgaos_detalhe (já extraído com dataInicio/dataFim)
            gold_org = self.base_dir / "gold" / "orgaos" / "orgaos.parquet"
            gold_det = self.base_dir / "gold" / "orgaos_detalhe" / "orgaos_detalhe.parquet"
            if gold_org.exists() and gold_det.exists():
                path_org = str(gold_org).replace("'", "''")
                path_det = str(gold_det).replace("'", "''")
                sql = (
                    f"SELECT DISTINCT o.id FROM read_parquet('{path_org}') o "
                    f"JOIN read_parquet('{path_det}') d ON o.id = d.id "
                    f"WHERE CAST(d.dataInicio AS VARCHAR) <= '{hi}' "
                    f"AND (d.dataFim IS NULL OR CAST(d.dataFim AS VARCHAR) >= '{lo}') "
                    f"ORDER BY o.id"
                )
                result = con.execute(sql).df()
                ids = result["id"].tolist() if not result.empty else []
                logger.info(
                    "[DataLakeRepository] DuckDB Gold: %s orgaos ativos (%s..%s).",
                    len(ids),
                    lo,
                    hi,
                )
                return ids

            # ── Fallback: Silver ─────────────────────────────────────────────
            sil_org = self.base_dir / "silver" / "orgaos"
            sil_det = self.base_dir / "silver" / "orgaos_detalhe"
            if sil_org.exists() and sil_det.exists():
                sil_org_path = str(sil_org).replace(chr(39), chr(39) + chr(39))
                sil_det_path = str(sil_det).replace(chr(39), chr(39) + chr(39))
                sql = (
                    f"SELECT DISTINCT o.id FROM read_parquet('{sil_org_path}/*.parquet') o "
                    f"JOIN read_parquet('{sil_det_path}/*.parquet') d ON o.id = d.id "
                    f"WHERE CAST(d.dataInicio AS VARCHAR) <= '{hi}' "
                    f"AND (d.dataFim IS NULL OR CAST(d.dataFim AS VARCHAR) >= '{lo}') "
                    f"ORDER BY o.id"
                )
                result = con.execute(sql).df()
                ids = result["id"].tolist() if not result.empty else []
                logger.info(
                    "[DataLakeRepository] DuckDB Silver: %s orgaos ativos (%s..%s).",
                    len(ids),
                    lo,
                    hi,
                )
                return ids

            # Fallback final: sem dados, retorna todos
            logger.warning(
                "[DataLakeRepository] orgaos_detalhe indisponivel"
                " (Gold nem Silver); sem filtro temporal."
            )
            return self.list_orgao_ids_silver_or_gold()
        except Exception as e:
            logger.error(
                "[DataLakeRepository] Falha DuckDB orgaos_in_window: %s. Fallback todos.", e
            )
            return self.list_orgao_ids_silver_or_gold()
        finally:
            con.close()

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
        self, table_name: str, parent_id_column: str = "id"
    ) -> set[Any]:
        """Return set of parent IDs whose child records already exist in Silver or Gold.

        Tries the provided column first; if the column does not exist (e.g. Senado
        tables use ``codigo`` instead of ``id``), falls back to ``codigo``.
        """

        def _try_col(col: str) -> set[Any]:
            return set(self.list_ids(table_name, "silver", col)) | set(
                self.list_ids(table_name, "gold", col)
            )

        result = _try_col(parent_id_column)
        if not result:
            fallback = _try_col("codigo")
            if fallback:
                return fallback
        return result

    def list_evento_ids_silver_or_gold(
        self,
        start_iso: str | None = None,
        end_iso: str | None = None,
    ) -> List[Any]:
        if start_iso and end_iso:
            ids = self._list_ids_in_window(
                DomainType.EVENTOS.value, "dataHoraInicio", "silver", start_iso, end_iso
            )
            if ids:
                return ids
            return self._list_ids_in_window(
                DomainType.EVENTOS.value, "dataHoraInicio", "gold", start_iso, end_iso
            )
        return self.list_ids(DomainType.EVENTOS.value, "silver", "id") or self.list_ids(
            DomainType.EVENTOS.value, "gold", "id"
        )

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

    def list_deputy_legislature_windows(
        self,
        earliest_start: str = "1995-01-01",
    ) -> list[tuple[int, str, str]]:
        """
        Pares (id_deputado, dataInicio, dataFim) para cada legislatura ativa por deputado.

        Faz o JOIN entre gold/legislaturas e gold/deputados_historico (ou Silver como
        fallback) para obter a janela temporal real de cada legislatura que cada
        deputado serviu. Cada legislatura tem ≤4 anos, eliminando a necessidade de
        chunking temporal na extração de discursos/orgaos/eventos por deputado.

        Args:
            earliest_start: Data ISO mínima para filtrar legislaturas com
                ``dataFim >= earliest_start`` (padrão ``1995-01-01``, data a partir
                da qual discursos digitalizados existem).

        Returns:
            Lista de tuplas (id_deputado, dataInicio, dataFim) ordenadas por
            deputado e data de início da legislatura, ou lista vazia se os dados
            de origem não estiverem disponíveis.
        """
        leg_table = DomainType.LEGISLATURAS.value
        hist_table = DomainType.DEPUTADOS_HISTORICO.value

        con = duckdb.connect(database=":memory:")
        try:
            # ── Tenta Gold primeiro ──────────────────────────────────────────
            gold_leg = self.base_dir / "gold" / leg_table / f"{leg_table}.parquet"
            gold_hist = self.base_dir / "gold" / hist_table / f"{hist_table}.parquet"
            if gold_leg.exists() and gold_hist.exists():
                sql = (
                    f"SELECT DISTINCT h.id_deputado,"
                    f" CAST(l.dataInicio AS VARCHAR),"
                    f" CAST(l.dataFim AS VARCHAR) "
                    f"FROM read_parquet('{str(gold_hist).replace(chr(39), chr(39) + chr(39))}') h "
                    f"JOIN read_parquet('{str(gold_leg).replace(chr(39), chr(39) + chr(39))}') l "
                    f"  ON CAST(h.idLegislatura AS BIGINT) = l.id "
                    f"WHERE CAST(l.dataFim AS VARCHAR) >= '{earliest_start}' "
                    f"ORDER BY h.id_deputado, l.id"
                )
                result = con.execute(sql).fetchall()
                if result:
                    pairs = [(int(r[0]), str(r[1]), str(r[2])) for r in result]
                    logger.info(
                        "[DataLakeRepository] DuckDB Gold: %s pares deputado-legislatura (≥%s).",
                        len(pairs),
                        earliest_start[:10],
                    )
                    return pairs

            # ── Fallback: Silver ─────────────────────────────────────────────
            sil_leg = self.base_dir / "silver" / leg_table
            sil_hist = self.base_dir / "silver" / hist_table
            if sil_leg.exists() and sil_hist.exists():
                leg_glob = str(sil_leg / "*.parquet")
                hist_glob = str(sil_hist / "*.parquet")
                sql = (
                    f"SELECT DISTINCT h.id_deputado,"
                    f" CAST(l.dataInicio AS VARCHAR),"
                    f" CAST(l.dataFim AS VARCHAR) "
                    f"FROM read_parquet('{hist_glob}') h "
                    f"JOIN read_parquet('{leg_glob}') l "
                    f"  ON CAST(h.idLegislatura AS BIGINT) = l.id "
                    f"WHERE CAST(l.dataFim AS VARCHAR) >= '{earliest_start}' "
                    f"ORDER BY h.id_deputado, l.id"
                )
                result = con.execute(sql).fetchall()
                if result:
                    pairs = [(int(r[0]), str(r[1]), str(r[2])) for r in result]
                    logger.info(
                        "[DataLakeRepository] DuckDB Silver: %s pares deputado-legislatura (≥%s).",
                        len(pairs),
                        earliest_start[:10],
                    )
                    return pairs

            logger.warning(
                "[DataLakeRepository] Nenhum dado de legislaturas ou deputados_historico "
                "disponível (Gold nem Silver)."
            )
            return []
        except Exception as e:
            logger.error(
                "[DataLakeRepository] Falha no JOIN legislaturas × deputados_historico: %s",
                e,
            )
            return []
        finally:
            con.close()

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
