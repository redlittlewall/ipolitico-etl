import logging
from pathlib import Path

import duckdb

from ipolitico.core.constants import ApiParams, DomainType, MedallionLayer
from ipolitico.core.schemas import despesas_optimizer_partition_sql

logger = logging.getLogger(__name__)


class DataLakeOptimizer:
    """
    Motor de Compactação e Governança Out-of-Core usando DuckDB.
    Resolve o 'Small Files Problem' e aplica UPSERT analítico (deduplicação).
    """

    def __init__(self, base_dir: str = "data/datalake"):
        self.base_dir = Path(base_dir)

    def compact_and_deduplicate(
        self,
        table_name: str,
        source_layer: str = MedallionLayer.SILVER,
        target_layer: str = MedallionLayer.GOLD,
    ):
        source_dir = self.base_dir / source_layer / table_name
        if not source_dir.exists() or not list(source_dir.glob("*.parquet")):
            logger.warning(
                "[%s] Sem arquivos em %s; Gold não gerado (rode ingestão antes).",
                table_name.upper(),
                source_dir,
            )
            return

        source_path = source_dir / "*.parquet"
        target_dir = self.base_dir / target_layer / table_name
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / f"{table_name}.parquet"

        con = duckdb.connect(database=":memory:")

        logger.info(f"[{table_name.upper()}] Iniciando compactação e deduplicação Out-of-Core...")

        try:
            if table_name == DomainType.DESPESAS.value:
                pk_cols = despesas_optimizer_partition_sql()
            elif table_name in [
                DomainType.DEPUTADOS.value,
                DomainType.PROPOSICOES.value,
                DomainType.VOTACOES.value,
                DomainType.ORGAOS.value,
                DomainType.PARTIDOS.value,
                DomainType.EVENTOS.value,
            ]:
                pk_cols = ApiParams.ID.value
            elif table_name == DomainType.VOTOS.value:
                pk_cols = f"votacao_id, {ApiParams.DEPUTADO_ID.value}"
            else:
                pk_cols = ApiParams.ID.value

            query = f"""
            COPY (
                SELECT * EXCLUDE (rn) FROM (
                    SELECT
                        *,
                        ROW_NUMBER() OVER (
                            PARTITION BY {pk_cols}
                            ORDER BY captured_at DESC
                        ) as rn
                    FROM read_parquet('{source_path}')
                ) WHERE rn = 1
            ) TO '{target_file}' (FORMAT PARQUET, COMPRESSION 'ZSTD');
            """

            con.execute(query)
            logger.info(
                f"[{table_name.upper()}] Camada {target_layer.upper()}"
                f" gerada com sucesso em {target_file}"
            )

        except duckdb.Error as e:
            logger.error(f"[{table_name.upper()}] Falha na Compactação DuckDB: {e}")
        finally:
            con.close()


if __name__ == "__main__":
    # Teste Rápido
    logging.basicConfig(level=logging.INFO)
    opt = DataLakeOptimizer()
    opt.compact_and_deduplicate("despesas")
    opt.compact_and_deduplicate("deputados")
    opt.compact_and_deduplicate("proposicoes")
    opt.compact_and_deduplicate("votacoes")
    opt.compact_and_deduplicate("votos")
