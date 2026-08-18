import logging
from pathlib import Path

import duckdb

from ipolitico.core.constants import MedallionLayer
from ipolitico.core.schemas import despesas_optimizer_partition_sql

logger = logging.getLogger(__name__)

_EXCLUDED_COLS_DEDUP = frozenset({"captured_at", "rn"})


class DataLakeOptimizer:
    """
    Motor de Compactação e Governança Out-of-Core usando DuckDB.
    Resolve o 'Small Files Problem' e aplica UPSERT analítico (deduplicação).

    A chave de partição para deduplicação é determinada por introspecção:
      - Se houver coluna ``id`` → `PARTITION BY id`
        (domínios entidade: mantém o snapshot mais recente por entidade)
      - Senão → `PARTITION BY todas_colunas_exceto_metadados`
        (domínios evento: linhas imutáveis; duplicatas = linhas idênticas)
    """

    def __init__(self, base_dir: str = "data/datalake"):
        self.base_dir = Path(base_dir)

    @staticmethod
    def _resolve_pk_cols(source_path: Path) -> str:
        """Define a cláusula PARTITION BY inspecionando o schema dos parquet.

        Regras:
          1. Se existir coluna ``id`` com valores **não-nulos** → ``PARTITION BY id``.
             Se ``id`` for 100 % null (schema fantasma) → cai para regra 3.
          2. Se existir ``id_deputado`` e ``votacao_id`` (tabela de votos) →
             ``PARTITION BY votacao_id, id_deputado``.
          3. Caso contrário → ``PARTITION BY`` todas as colunas exceto metadados
             (dedup exato de linha).

        A verificação de nulidade impede que colunas ``id`` sempre-nulas (criadas
        por schema contracts que a API não preenche) colapsem todos os registros
        em uma única partição.
        """
        conn = duckdb.connect(database=":memory:")
        try:
            cols = [
                row[0]
                for row in conn.execute(
                    "SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet('{}'))".format(
                        source_path
                    )
                ).fetchall()
                if row[0] not in _EXCLUDED_COLS_DEDUP
            ]

            if "id" in cols:
                total = conn.execute(
                    "SELECT COUNT(*) FROM read_parquet('{}')".format(source_path)
                ).fetchone()[0]
                nulls = conn.execute(
                    "SELECT COUNT(*) FROM read_parquet('{}') WHERE id IS NULL".format(source_path)
                ).fetchone()[0]
                if nulls < total or total == 0:
                    return "id"
                cols.remove("id")

            if "id_deputado" in cols and "votacao_id" in cols:
                return "votacao_id, id_deputado"

            return ", ".join(cols)
        finally:
            conn.close()

    def compact_and_deduplicate(
        self,
        table_name: str,
        source_layer: str = MedallionLayer.SILVER,
        target_layer: str = MedallionLayer.GOLD,
        pk_cols: str | None = None,
    ) -> None:
        """Consolida e deduplica uma tabela Parquet entre camadas (out-of-core).

        Args:
            table_name: Nome da tabela/entidade (diretório da camada origem).
            source_layer: Camada de leitura (``silver``, ``bronze`` ou ``gold``).
            target_layer: Camada de escrita do arquivo deduplicado.
            pk_cols: Cláusula ``PARTITION BY`` explícita (ex.: ``"politico_id"``
                ou ``"fonte, id_natural"``). Quando fornecida, ignora a introspecção
                de chave. Quando ``None``, resolve por introspecção
                (``_resolve_pk_cols`` / caso especial ``despesas``).

        Returns:
            None. Escreve ``{target_layer}/{table_name}/{table_name}.parquet``
            deduplicado, ou loga aviso sem criar nada se a origem estiver vazia.
        """
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

        logger.info(f"[{table_name.upper()}] Iniciando compactação e deduplicação Out-of-Core...")

        try:
            if pk_cols is not None:
                partition_cols = pk_cols
            elif table_name == "despesas":
                partition_cols = despesas_optimizer_partition_sql()
            else:
                partition_cols = self._resolve_pk_cols(source_path)

            query = f"""
            COPY (
                SELECT * EXCLUDE (rn) FROM (
                    SELECT
                        *,
                        ROW_NUMBER() OVER (
                            PARTITION BY {partition_cols}
                            ORDER BY captured_at DESC
                        ) as rn
                    FROM read_parquet('{source_path}')
                ) WHERE rn = 1
            ) TO '{target_file}' (FORMAT PARQUET, COMPRESSION 'ZSTD');
            """

            with duckdb.connect(database=":memory:") as con:
                con.execute(query)
            logger.info(
                f"[{table_name.upper()}] Camada {target_layer.upper()}"
                f" gerada com sucesso em {target_file}"
            )

        except duckdb.Error as e:
            logger.error(f"[{table_name.upper()}] Falha na Compactação DuckDB: {e}")


if __name__ == "__main__":
    # Teste Rápido
    logging.basicConfig(level=logging.INFO)
    opt = DataLakeOptimizer()
    opt.compact_and_deduplicate("despesas")
    opt.compact_and_deduplicate("deputados")
    opt.compact_and_deduplicate("proposicoes")
    opt.compact_and_deduplicate("votacoes")
    opt.compact_and_deduplicate("votos")
